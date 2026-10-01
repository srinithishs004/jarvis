from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


BACKUP_FORMAT_VERSION = 1


class BackupRecord(BaseModel):
    table: str = Field(min_length=1)
    row: dict[str, Any]


class RedisBackupEntry(BaseModel):
    key: str = Field(min_length=1)
    value: Any


class BackupManifest(BaseModel):
    format_version: int = BACKUP_FORMAT_VERSION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    postgres: dict[str, int] = Field(default_factory=dict)
    redis: dict[str, int] = Field(default_factory=dict)


class JarvisBackup(BaseModel):
    manifest: BackupManifest
    postgres: list[BackupRecord] = Field(default_factory=list)
    redis: list[RedisBackupEntry] = Field(default_factory=list)

    @classmethod
    def empty(cls) -> "JarvisBackup":
        return cls(manifest=BackupManifest())
