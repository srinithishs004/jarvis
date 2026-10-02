from datetime import datetime, timezone
import pytest

from app.backup.archive import BackupArchive, BackupArchiveError
from app.models.backup import BackupManifest, JarvisBackup


def make_backup(created_at: datetime) -> JarvisBackup:
    return JarvisBackup(
        manifest=BackupManifest(created_at=created_at),
    )


def test_write_backup_uses_manifest_timestamp_and_atomic_replace(tmp_path):
    archive = BackupArchive(tmp_path)
    backup = make_backup(datetime(2026, 10, 2, 16, 30, tzinfo=timezone.utc))

    path = archive.write(backup)

    assert path == tmp_path / "jarvis-backup-20261002T163000Z.json"
    assert path.exists()
    assert path.read_text().startswith("{")
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_rejects_invalid_backup(tmp_path):
    archive = BackupArchive(tmp_path)

    backup = JarvisBackup(
        manifest=BackupManifest(format_version=999),
    )

    with pytest.raises(BackupArchiveError, match="Invalid backup"):
        archive.write(backup)


def test_retention_keeps_seven_daily_and_four_weekly(tmp_path):
    archive = BackupArchive(tmp_path)

    timestamps = [
        datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc),
    ]

    for timestamp in timestamps:
        archive.write(make_backup(timestamp))

    result = archive.apply_retention()

    assert result["deleted"] >= 1
    assert result["remaining"] == 10


def test_retention_does_not_delete_non_backup_files(tmp_path):
    archive = BackupArchive(tmp_path)
    marker = tmp_path / "keep.txt"
    marker.write_text("do not delete")

    archive.write(
        make_backup(datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc))
    )
    archive.apply_retention()

    assert marker.exists()
    assert marker.read_text() == "do not delete"


def test_list_backups_ignores_invalid_files(tmp_path):
    archive = BackupArchive(tmp_path)

    archive.write(
        make_backup(datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc))
    )
    (tmp_path / "jarvis-backup-bad.json").write_text("{}")

    backups = archive.list_backups()

    assert len(backups) == 1
    assert backups[0].name == "jarvis-backup-20261002T120000Z.json"
