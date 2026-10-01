from __future__ import annotations

import os

from app.backup.adapters import PostgresBackupAdapter, RedisBackupAdapter
from app.backup.service import BackupService


def create_backup_service() -> BackupService:
    postgres = PostgresBackupAdapter(
        os.environ["SUPABASE_DB_URL"],
    )

    redis = RedisBackupAdapter()

    return BackupService(
        postgres_export=postgres.export,
        postgres_restore=postgres.restore,
        redis_export=redis.export,
        redis_restore=redis.restore,
    )
