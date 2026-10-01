import pytest

from app.backup.service import BackupError, BackupService
from app.models.backup import (
    BackupManifest,
    BackupRecord,
    JarvisBackup,
    RedisBackupEntry,
)


def test_create_backup_collects_postgres_and_redis():
    service = BackupService(
        postgres_export=lambda: [
            {"table": "tasks", "row": {"id": "task-1", "status": "succeeded"}},
            {
                "table": "audit_events",
                "row": {"id": 1, "event_type": "tool_execution"},
            },
        ],
        redis_export=lambda prefixes, exact_keys: [
            {"key": "jarvis:task:task-1", "value": {"status": "succeeded"}},
            {"key": "jarvis:session:session-1", "value": {"messages": []}},
            {"key": "jarvis:kill-switch", "value": {"active": False}},
        ],
    )

    backup = service.create_backup()

    assert backup.manifest.format_version == 1
    assert backup.manifest.postgres == {
        "tasks": 1,
        "audit_events": 1,
    }
    assert backup.manifest.redis == {"entries": 3}
    assert len(backup.postgres) == 2
    assert len(backup.redis) == 3


def test_serialize_and_deserialize_round_trip():
    service = BackupService()

    backup = JarvisBackup(
        manifest=BackupManifest(),
        postgres=[
            BackupRecord(
                table="tasks",
                row={"id": "task-1", "status": "succeeded"},
            )
        ],
        redis=[
            RedisBackupEntry(
                key="jarvis:session:session-1",
                value={"messages": []},
            )
        ],
    )

    payload = service.serialize(backup)
    restored = service.deserialize(payload)

    assert restored == backup


def test_rejects_unsupported_postgres_table():
    service = BackupService()

    backup = JarvisBackup(
        manifest=BackupManifest(),
        postgres=[
            BackupRecord(
                table="users",
                row={"id": "secret"},
            )
        ],
    )

    with pytest.raises(BackupError, match="Unsupported PostgreSQL table"):
        service.validate(backup)


def test_rejects_unsupported_redis_key():
    service = BackupService()

    backup = JarvisBackup(
        manifest=BackupManifest(),
        redis=[
            RedisBackupEntry(
                key="unrelated:key",
                value={"data": "x"},
            )
        ],
    )

    with pytest.raises(BackupError, match="Unsupported Redis key"):
        service.validate(backup)


def test_rejects_unsupported_backup_version():
    service = BackupService()

    backup = JarvisBackup(
        manifest=BackupManifest(format_version=999),
    )

    with pytest.raises(BackupError, match="Unsupported backup format version"):
        service.validate(backup)


def test_restore_validates_before_writing():
    postgres_calls = []
    redis_calls = []

    service = BackupService(
        postgres_restore=lambda rows: postgres_calls.append(rows),
        redis_restore=lambda entries: redis_calls.append(entries),
    )

    backup = JarvisBackup(
        manifest=BackupManifest(),
        postgres=[
            BackupRecord(
                table="not_allowed",
                row={"id": "bad"},
            )
        ],
    )

    with pytest.raises(BackupError):
        service.restore(backup)

    assert postgres_calls == []
    assert redis_calls == []


def test_restore_delegates_validated_data():
    postgres_calls = []
    redis_calls = []

    service = BackupService(
        postgres_restore=lambda rows: postgres_calls.append(rows),
        redis_restore=lambda entries: redis_calls.append(entries),
    )

    backup = JarvisBackup(
        manifest=BackupManifest(),
        postgres=[
            BackupRecord(
                table="tasks",
                row={"id": "task-1"},
            )
        ],
        redis=[
            RedisBackupEntry(
                key="jarvis:task:task-1",
                value={"status": "succeeded"},
            )
        ],
    )

    service.restore(backup)

    assert postgres_calls == [
        [{"table": "tasks", "row": {"id": "task-1"}}]
    ]
    assert redis_calls == [
        [
            {
                "key": "jarvis:task:task-1",
                "value": {"status": "succeeded"},
            }
        ]
    ]


def test_backup_without_adapters_is_valid_empty_backup():
    backup = BackupService().create_backup()

    assert backup.postgres == []
    assert backup.redis == []
    assert backup.manifest.postgres == {}
    assert backup.manifest.redis == {"entries": 0}
