from datetime import datetime, timezone

import app.backup.runner as runner
from app.models.backup import BackupManifest, JarvisBackup


class FakeBackupService:
    def __init__(self):
        self.created = False

    def create_backup(self):
        self.created = True
        return JarvisBackup(
            manifest=BackupManifest(
                created_at=datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc),
            )
        )


class FakeArchive:
    def __init__(
        self,
        directory,
        *,
        backup_service,
        daily_retention,
        weekly_retention,
    ):
        self.directory = directory
        self.backup_service = backup_service
        self.daily_retention = daily_retention
        self.weekly_retention = weekly_retention
        self.written = None

    def write(self, backup):
        self.written = backup
        return self.directory / "jarvis-backup-20261002T180000Z.json"

    def apply_retention(self):
        return {"deleted": 2, "remaining": 9}


def test_run_backup_creates_archive_and_applies_retention(monkeypatch, tmp_path):
    service = FakeBackupService()

    monkeypatch.setattr(
        runner,
        "create_backup_service",
        lambda: service,
    )
    monkeypatch.setattr(
        runner,
        "BackupArchive",
        FakeArchive,
    )
    monkeypatch.setattr(
        runner,
        "load_dotenv",
        lambda _: None,
    )

    result = runner.run_backup(
        env_file=str(tmp_path / ".env"),
        backup_directory=tmp_path / "backups",
    )

    assert service.created is True
    assert result == {
        "ok": True,
        "path": str(
            tmp_path / "backups" / "jarvis-backup-20261002T180000Z.json"
        ),
        "format_version": 1,
        "created_at": "2026-10-02T18:00:00+00:00",
        "postgres": {},
        "redis": {},
        "retention": {
            "deleted": 2,
            "remaining": 9,
        },
    }


def test_run_backup_loads_requested_env_file(monkeypatch, tmp_path):
    captured = []

    monkeypatch.setattr(
        runner,
        "load_dotenv",
        lambda env_file: captured.append(env_file),
    )
    monkeypatch.setattr(
        runner,
        "create_backup_service",
        FakeBackupService,
    )
    monkeypatch.setattr(
        runner,
        "BackupArchive",
        FakeArchive,
    )

    env_file = tmp_path / "custom.env"

    runner.run_backup(
        env_file=str(env_file),
        backup_directory=tmp_path / "backups",
    )

    assert captured == [str(env_file)]
