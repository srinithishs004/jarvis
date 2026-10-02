from psycopg.types.json import Jsonb

from app.backup.adapters import PostgresBackupAdapter, RedisBackupAdapter


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.description = [
            type("Column", (), {"name": "id"})(),
            type("Column", (), {"name": "status"})(),
        ]
        self.rows = [
            ("task-1", "succeeded"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl_seconds=None):
        self.values[key] = value

    def scan(self, cursor=0, match=None, count=None):
        keys = list(self.values)

        if match is not None:
            prefix = match.removesuffix("*")
            keys = [key for key in keys if key.startswith(prefix)]

        return 0, keys


def test_redis_adapter_exports_exact_keys():
    redis = FakeRedis()
    redis.values["jarvis:kill-switch"] = {"active": True}

    adapter = RedisBackupAdapter(redis)

    entries = adapter.export(
        prefixes=("jarvis:task:", "jarvis:session:"),
        exact_keys=("jarvis:kill-switch",),
    )

    assert entries == [
        {
            "key": "jarvis:kill-switch",
            "value": {"active": True},
        }
    ]


def test_redis_adapter_ignores_missing_exact_keys():
    adapter = RedisBackupAdapter(FakeRedis())

    entries = adapter.export(
        prefixes=(),
        exact_keys=("jarvis:kill-switch",),
    )

    assert entries == []


def test_redis_adapter_restores_entries():
    redis = FakeRedis()
    adapter = RedisBackupAdapter(redis)

    adapter.restore(
        [
            {
                "key": "jarvis:kill-switch",
                "value": {"active": True},
            },
        ]
    )

    assert redis.values["jarvis:kill-switch"] == {"active": True}


def test_postgres_adapter_export_reads_table_rows(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    def fake_connect(database_url, connect_timeout):
        assert database_url == "postgres://test"
        assert connect_timeout == 5
        return connection

    monkeypatch.setattr(
        "app.backup.adapters.psycopg.connect",
        fake_connect,
    )

    adapter = PostgresBackupAdapter("postgres://test")
    records = adapter.export()

    assert records == [
        {
            "table": "tasks",
            "row": {
                "id": "task-1",
                "status": "succeeded",
            },
        },
        {
            "table": "audit_events",
            "row": {
                "id": "task-1",
                "status": "succeeded",
            },
        },
    ]


def test_postgres_adapter_restore_commits(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    def fake_connect(database_url, connect_timeout):
        return connection

    monkeypatch.setattr(
        "app.backup.adapters.psycopg.connect",
        fake_connect,
    )

    adapter = PostgresBackupAdapter("postgres://test")

    adapter.restore(
        [
            {
                "table": "tasks",
                "row": {
                    "id": "task-1",
                    "status": "succeeded",
                },
            }
        ]
    )

    assert connection.committed is True
    assert len(cursor.executed) == 1
    query, params = cursor.executed[0]
    assert "INSERT INTO tasks" in query
    assert params == ["task-1", "succeeded"]


class ScanningFakeRedis(FakeRedis):
    def __init__(self):
        super().__init__()
        self.scan_calls = []

    def scan(self, cursor=0, match=None, count=None):
        self.scan_calls.append((cursor, match, count))

        if cursor == 0:
            return 1, [
                "jarvis:task:task-1",
                "jarvis:session:session-1",
            ]

        return 0, [
            "jarvis:task:task-1",
            "jarvis:session:session-2",
        ]


def test_redis_adapter_exports_prefix_keys_across_scan_pages():
    redis = ScanningFakeRedis()
    redis.values.update(
        {
            "jarvis:task:task-1": {"status": "succeeded"},
            "jarvis:session:session-1": {"messages": []},
            "jarvis:session:session-2": {"messages": [{"role": "user"}]},
        }
    )

    adapter = RedisBackupAdapter(redis)

    entries = adapter.export(
        prefixes=("jarvis:task:", "jarvis:session:"),
        exact_keys=(),
    )

    assert entries == [
        {
            "key": "jarvis:task:task-1",
            "value": {"status": "succeeded"},
        },
        {
            "key": "jarvis:session:session-1",
            "value": {"messages": []},
        },
        {
            "key": "jarvis:session:session-2",
            "value": {"messages": [{"role": "user"}]},
        },
    ]


def test_redis_adapter_does_not_duplicate_exact_key():
    redis = ScanningFakeRedis()
    redis.values["jarvis:task:task-1"] = {"status": "succeeded"}

    adapter = RedisBackupAdapter(redis)

    entries = adapter.export(
        prefixes=("jarvis:task:",),
        exact_keys=("jarvis:task:task-1",),
    )

    assert entries == [
        {
            "key": "jarvis:task:task-1",
            "value": {"status": "succeeded"},
        }
    ]


def test_redis_adapter_skips_missing_values():
    redis = ScanningFakeRedis()

    adapter = RedisBackupAdapter(redis)

    entries = adapter.export(
        prefixes=("jarvis:task:",),
        exact_keys=("jarvis:kill-switch",),
    )

    assert entries == []


def test_postgres_adapter_restore_adapts_json_values(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    def fake_connect(database_url, connect_timeout):
        return connection

    monkeypatch.setattr(
        "app.backup.adapters.psycopg.connect",
        fake_connect,
    )

    adapter = PostgresBackupAdapter("postgres://test")

    adapter.restore(
        [
            {
                "table": "tasks",
                "row": {
                    "id": "task-1",
                    "metadata": {"source": "backup"},
                },
            }
        ]
    )

    query, params = cursor.executed[0]

    assert params[0] == "task-1"
    assert isinstance(params[1], Jsonb)
    assert params[1].obj == {"source": "backup"}
