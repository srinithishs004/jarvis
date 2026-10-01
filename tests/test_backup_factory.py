from app.backup.adapters import PostgresBackupAdapter, RedisBackupAdapter
from app.backup.factory import create_backup_service


def test_create_backup_service_wires_real_adapters(monkeypatch):
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgres://example",
    )
    monkeypatch.setenv(
        "UPSTASH_REDIS_REST_URL",
        "https://example.upstash.io",
    )
    monkeypatch.setenv(
        "UPSTASH_REDIS_REST_TOKEN",
        "test-token",
    )

    service = create_backup_service()

    assert service.postgres_export.__self__.__class__ is PostgresBackupAdapter
    assert service.postgres_restore.__self__.__class__ is PostgresBackupAdapter
    assert service.redis_export.__self__.__class__ is RedisBackupAdapter
    assert service.redis_restore.__self__.__class__ is RedisBackupAdapter
