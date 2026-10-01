from app.redis.task_state import TaskStateStore


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.ttls = {}

    def set(self, key, value, ttl_seconds=None):
        self.data[key] = value
        self.ttls[key] = ttl_seconds

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        self.data.pop(key, None)


def test_task_state_save_and_get():
    store = TaskStateStore(redis=FakeRedis())

    class Task:
        task_id = "test-task"
        status = type("Status", (), {"value": "running"})()
        cancel_requested = False

    store.save(Task())

    state = store.get("test-task")

    assert state["task_id"] == "test-task"
    assert state["status"] == "running"
    assert state["cancel_requested"] is False
    assert state["worker_id"] is None


def test_task_state_passes_ttl():
    fake = FakeRedis()
    store = TaskStateStore(redis=fake)

    class Task:
        task_id = "ttl-task"
        status = type("Status", (), {"value": "running"})()
        cancel_requested = False

    store.save(Task(), ttl_seconds=30)

    assert fake.ttls["jarvis:task:ttl-task"] == 30


def test_task_state_stores_worker_id():
    fake = FakeRedis()
    store = TaskStateStore(redis=fake)

    class Task:
        task_id = "worker-task"
        status = type("Status", (), {"value": "running"})()
        cancel_requested = False

    store.save(Task(), worker_id="worker-123")

    state = store.get("worker-task")

    assert state["worker_id"] == "worker-123"


def test_task_lease_acquire_and_get():
    fake = FakeRedis()
    store = TaskStateStore(redis=fake)

    store.acquire_lease("lease-task", "worker-123", ttl_seconds=15)

    lease = store.get_lease("lease-task")

    assert lease["task_id"] == "lease-task"
    assert lease["worker_id"] == "worker-123"
    assert fake.ttls["jarvis:task-lease:lease-task"] == 15


def test_task_lease_renew_rejects_other_worker():
    fake = FakeRedis()
    store = TaskStateStore(redis=fake)

    store.acquire_lease("lease-task", "worker-123")

    try:
        store.renew_lease("lease-task", "worker-456")
    except RuntimeError as exc:
        assert "another worker" in str(exc)
    else:
        raise AssertionError("Expected lease ownership error")


def test_task_lease_release():
    fake = FakeRedis()
    store = TaskStateStore(redis=fake)

    store.acquire_lease("lease-task", "worker-123")
    store.release_lease("lease-task")

    assert store.get_lease("lease-task") is None


def test_task_lease_contains_expiry():
    fake = FakeRedis()
    store = TaskStateStore(redis=fake)

    store.acquire_lease("expiry-task", "worker-123", ttl_seconds=15)

    lease = store.get_lease("expiry-task")

    assert lease["worker_id"] == "worker-123"
    assert lease["lease_expires_at"]


def test_task_lease_renew_updates_expiry():
    fake = FakeRedis()
    store = TaskStateStore(redis=fake)

    store.acquire_lease("renew-task", "worker-123", ttl_seconds=15)
    first = store.get_lease("renew-task")["lease_expires_at"]

    store.renew_lease("renew-task", "worker-123", ttl_seconds=30)
    second = store.get_lease("renew-task")["lease_expires_at"]

    assert first != second


def test_redis_store_scan_builds_command_and_parses_response(monkeypatch):
    from app.redis.store import RedisStore

    store = object.__new__(RedisStore)
    calls = []

    def fake_request(command):
        calls.append(command)
        return ["2", ["jarvis:task:1", "jarvis:task:2"]]

    store._request = fake_request

    cursor, keys = store.scan(
        cursor=0,
        match="jarvis:task:*",
        count=100,
    )

    assert calls == [["SCAN", 0, "MATCH", "jarvis:task:*", "COUNT", 100]]
    assert cursor == 2
    assert keys == ["jarvis:task:1", "jarvis:task:2"]


def test_redis_store_scan_rejects_invalid_response():
    from app.redis.store import RedisStore

    store = object.__new__(RedisStore)
    store._request = lambda command: {"bad": "response"}

    import pytest

    with pytest.raises(RuntimeError, match="Invalid Redis SCAN response"):
        store.scan()
