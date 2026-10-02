from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.redis.store import RedisStore


class PostgresBackupAdapter:
    TABLES = ("tasks", "audit_events")
    ALLOWED_TABLES = frozenset(TABLES)

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def export(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        with psycopg.connect(self.database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for table in self.TABLES:
                    cur.execute(f"SELECT * FROM {table}")
                    columns = [column.name for column in cur.description]

                    for row in cur.fetchall():
                        records.append(
                            {
                                "table": table,
                                "row": dict(zip(columns, row)),
                            }
                        )

        return records

    def restore(self, records: list[dict[str, Any]]) -> None:
        with psycopg.connect(self.database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for record in records:
                    table = record["table"]
                    row = record["row"]

                    if table not in self.ALLOWED_TABLES:
                        raise ValueError(
                            f"Unsupported PostgreSQL table in backup: {table}"
                        )

                    columns = list(row.keys())

                    if not columns:
                        raise ValueError("Backup row must contain columns")

                    if any(
                        not column.replace("_", "").isalnum()
                        or not column[0].isalpha()
                        for column in columns
                    ):
                        raise ValueError(
                            f"Invalid PostgreSQL column identifier for {table}"
                        )

                    placeholders = ", ".join(["%s"] * len(columns))
                    column_sql = ", ".join(f'"{column}"' for column in columns)

                    values = [
                        Jsonb(row[column])
                        if isinstance(row[column], dict)
                        else row[column]
                        for column in columns
                    ]

                    cur.execute(
                        f"""
                        INSERT INTO {table} ({column_sql})
                        VALUES ({placeholders})
                        ON CONFLICT DO NOTHING
                        """,
                        values,
                    )

            conn.commit()


class RedisBackupAdapter:
    def __init__(self, redis: RedisStore | None = None) -> None:
        self.redis = redis or RedisStore()

    def export(
        self,
        prefixes: tuple[str, ...],
        exact_keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()

        for prefix in prefixes:
            cursor = 0

            while True:
                cursor, keys = self.redis.scan(
                    cursor=cursor,
                    match=f"{prefix}*",
                )

                for key in keys:
                    if key in seen:
                        continue

                    value = self.redis.get(key)
                    if value is not None:
                        entries.append({"key": key, "value": value})
                        seen.add(key)

                if cursor == 0:
                    break

        for key in exact_keys:
            if key in seen:
                continue

            value = self.redis.get(key)
            if value is not None:
                entries.append({"key": key, "value": value})
                seen.add(key)

        return entries

    def restore(self, entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            self.redis.set(
                entry["key"],
                entry["value"],
            )
