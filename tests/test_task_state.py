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
