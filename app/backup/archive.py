from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from app.backup.service import BackupError, BackupService
from app.models.backup import JarvisBackup


class BackupArchiveError(RuntimeError):
    """Raised when a backup cannot be archived or retained."""


class BackupArchive:
    FILE_PREFIX = "jarvis-backup-"
    FILE_SUFFIX = ".json"

    def __init__(
        self,
        directory: str | Path,
        *,
        backup_service: BackupService | None = None,
        daily_retention: int = 7,
        weekly_retention: int = 4,
    ) -> None:
        if daily_retention < 1:
            raise ValueError("daily_retention must be >= 1")
        if weekly_retention < 1:
            raise ValueError("weekly_retention must be >= 1")

        self.directory = Path(directory)
        self.backup_service = backup_service or BackupService()
        self.daily_retention = daily_retention
        self.weekly_retention = weekly_retention

    def write(self, backup: JarvisBackup) -> Path:
        try:
            self.backup_service.validate(backup)
        except BackupError as exc:
            raise BackupArchiveError(f"Invalid backup: {exc}") from exc

        self.directory.mkdir(parents=True, exist_ok=True)

        created_at = backup.manifest.created_at.astimezone(timezone.utc)
        filename = (
            f"{self.FILE_PREFIX}"
            f"{created_at.strftime('%Y%m%dT%H%M%SZ')}"
            f"{self.FILE_SUFFIX}"
        )

        destination = self.directory / filename
        temporary = self.directory / f".{filename}.tmp"

        payload = self.backup_service.serialize(backup)

        try:
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, destination)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise BackupArchiveError(
                f"Could not write backup archive: {destination}"
            ) from exc

        return destination

    def list_backups(self) -> list[Path]:
        if not self.directory.exists():
            return []

        backups: list[tuple[datetime, Path]] = []

        for path in self.directory.glob(
            f"{self.FILE_PREFIX}*{self.FILE_SUFFIX}"
        ):
            try:
                backup = self.backup_service.deserialize(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, BackupError):
                continue

            created_at = backup.manifest.created_at.astimezone(timezone.utc)
            backups.append((created_at, path))

        backups.sort(key=lambda item: item[0], reverse=True)
        return [path for _, path in backups]

    def apply_retention(self) -> dict[str, int]:
        backups = self.list_backups()

        daily_keep = self._latest_per_day(backups)[: self.daily_retention]
        daily_set = set(daily_keep)

        weekly_keep = [
            path
            for path in self._latest_per_week(backups)
            if path not in daily_set
        ][: self.weekly_retention]

        keep = daily_set | set(weekly_keep)

        deleted = 0

        for path in backups:
            if path in keep:
                continue

            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                raise BackupArchiveError(
                    f"Could not delete backup archive: {path}"
                ) from exc

        return {
            "deleted": deleted,
            "remaining": len(backups) - deleted,
        }

    def _latest_per_day(self, backups: list[Path]) -> list[Path]:
        selected: dict[tuple[int, int, int], Path] = {}

        for path in backups:
            created_at = self._created_at(path)
            key = (
                created_at.year,
                created_at.month,
                created_at.day,
            )
            selected.setdefault(key, path)

        return sorted(
            selected.values(),
            key=self._created_at,
            reverse=True,
        )

    def _latest_per_week(self, backups: list[Path]) -> list[Path]:
        selected: dict[tuple[int, int], Path] = {}

        for path in backups:
            created_at = self._created_at(path)
            iso = created_at.isocalendar()
            key = (iso.year, iso.week)
            selected.setdefault(key, path)

        return sorted(
            selected.values(),
            key=self._created_at,
            reverse=True,
        )

    def _created_at(self, path: Path) -> datetime:
        try:
            backup = self.backup_service.deserialize(
                path.read_text(encoding="utf-8")
            )
        except (OSError, BackupError) as exc:
            raise BackupArchiveError(
                f"Could not read backup archive: {path}"
            ) from exc

        return backup.manifest.created_at.astimezone(timezone.utc)
