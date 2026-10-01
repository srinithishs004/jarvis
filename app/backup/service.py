from __future__ import annotations

import json
from typing import Any, Callable

from app.models.backup import (
    BACKUP_FORMAT_VERSION,
    BackupManifest,
    BackupRecord,
    JarvisBackup,
    RedisBackupEntry,
)


class BackupError(RuntimeError):
    """Raised when a JARVIS backup cannot be created or restored."""


class BackupService:
    """
    Application-level backup/restore coordinator.

    Database and Redis operations are injected so backup/restore can be
    tested without requiring live infrastructure.
    """

    REQUIRED_POSTGRES_TABLES = ("tasks", "audit_events")
    REDIS_PREFIXES = (
        "jarvis:task:",
        "jarvis:session:",
    )
    REDIS_EXACT_KEYS = (
        "jarvis:kill-switch",
    )

    def __init__(
        self,
        *,
        postgres_export: Callable[[], list[dict[str, Any]]] | None = None,
        postgres_restore: Callable[[list[dict[str, Any]]], None] | None = None,
        redis_export: Callable[
            [tuple[str, ...], tuple[str, ...]], list[dict[str, Any]]
        ]
        | None = None,
        redis_restore: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> None:
        self.postgres_export = postgres_export
        self.postgres_restore = postgres_restore
        self.redis_export = redis_export
        self.redis_restore = redis_restore

    def create_backup(self) -> JarvisBackup:
        postgres_rows: list[BackupRecord] = []
        redis_entries: list[RedisBackupEntry] = []

        if self.postgres_export is not None:
            for item in self.postgres_export():
                table = item.get("table")
                row = item.get("row")

                if not isinstance(table, str) or not table:
                    raise BackupError("PostgreSQL backup row has invalid table")

                if not isinstance(row, dict):
                    raise BackupError(
                        f"PostgreSQL backup row for {table} is not an object"
                    )

                postgres_rows.append(
                    BackupRecord(
                        table=table,
                        row=row,
                    )
                )

        if self.redis_export is not None:
            for item in self.redis_export(
                self.REDIS_PREFIXES,
                self.REDIS_EXACT_KEYS,
            ):
                key = item.get("key")
                value = item.get("value")

                if not isinstance(key, str) or not key:
                    raise BackupError("Redis backup entry has invalid key")

                redis_entries.append(
                    RedisBackupEntry(
                        key=key,
                        value=value,
                    )
                )

        postgres_counts: dict[str, int] = {}
        for record in postgres_rows:
            postgres_counts[record.table] = (
                postgres_counts.get(record.table, 0) + 1
            )

        manifest = BackupManifest(
            format_version=BACKUP_FORMAT_VERSION,
            postgres=postgres_counts,
            redis={"entries": len(redis_entries)},
        )

        return JarvisBackup(
            manifest=manifest,
            postgres=postgres_rows,
            redis=redis_entries,
        )

    def serialize(self, backup: JarvisBackup) -> str:
        self.validate(backup)
        return json.dumps(
            backup.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )

    def deserialize(self, payload: str) -> JarvisBackup:
        try:
            backup = JarvisBackup.model_validate_json(payload)
        except Exception as exc:
            raise BackupError("Invalid JARVIS backup payload") from exc

        self.validate(backup)
        return backup

    def validate(self, backup: JarvisBackup) -> None:
        if backup.manifest.format_version != BACKUP_FORMAT_VERSION:
            raise BackupError(
                "Unsupported backup format version: "
                f"{backup.manifest.format_version}"
            )

        for record in backup.postgres:
            if record.table not in self.REQUIRED_POSTGRES_TABLES:
                raise BackupError(
                    f"Unsupported PostgreSQL table in backup: {record.table}"
                )

        for entry in backup.redis:
            if not self._redis_key_allowed(entry.key):
                raise BackupError(
                    f"Unsupported Redis key in backup: {entry.key}"
                )

    def restore(self, backup: JarvisBackup) -> None:
        self.validate(backup)

        if self.postgres_restore is not None:
            self.postgres_restore(
                [
                    {
                        "table": record.table,
                        "row": record.row,
                    }
                    for record in backup.postgres
                ]
            )

        if self.redis_restore is not None:
            self.redis_restore(
                [
                    {
                        "key": entry.key,
                        "value": entry.value,
                    }
                    for entry in backup.redis
                ]
            )

    def _redis_key_allowed(self, key: str) -> bool:
        if key in self.REDIS_EXACT_KEYS:
            return True

        return any(key.startswith(prefix) for prefix in self.REDIS_PREFIXES)
