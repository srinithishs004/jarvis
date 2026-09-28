from datetime import datetime, timedelta, timezone

from app.core.tasks import TaskManager
from app.models.task import Task, TaskStatus


class FakeRepository:
    def __init__(self, tasks):
        self.tasks = {task.task_id: task for task in tasks}
        self.updated = []

    def list_active(self):
        return list(self.tasks.values())

    def update(self, task):
        self.tasks[task.task_id] = task
        self.updated.append(task)


class FakeStateStore:
    def __init__(self, leases=None):
        self.leases = leases or {}
        self.saved = []
        self.released = []

    def get_lease(self, task_id):
        return self.leases.get(task_id)

    def save(self, task, worker_id=None):
        self.saved.append((task.task_id, task.status, worker_id))

    def release_lease(self, task_id):
        self.released.append(task_id)


def make_task(status, task_id):
    return Task(
        task_id=task_id,
        tool_name="test.recovery",
        status=status,
    )


def test_reconcile_keeps_queued_task():
    task = make_task(TaskStatus.QUEUED, "queued-1")
    repo = FakeRepository([task])
    state = FakeStateStore()

    manager = TaskManager(repository=repo, state_store=state)

    result = manager.reconcile_active_tasks()

    assert result["checked"] == 1
    assert result["queued"] == 1
    assert result["running_orphaned"] == 0
    assert repo.tasks["queued-1"].status == TaskStatus.QUEUED
    assert repo.updated == []


def test_reconcile_keeps_running_task_with_valid_lease():
    task = make_task(TaskStatus.RUNNING, "running-active")

    future = (
        datetime.now(timezone.utc) + timedelta(seconds=30)
    ).isoformat()

    repo = FakeRepository([task])
    state = FakeStateStore({
        "running-active": {
            "task_id": "running-active",
            "worker_id": "old-worker",
            "lease_expires_at": future,
        }
    })

    manager = TaskManager(repository=repo, state_store=state)

    result = manager.reconcile_active_tasks()

    assert result["running_active"] == 1
    assert result["running_orphaned"] == 0
    assert task.status == TaskStatus.RUNNING
    assert repo.updated == []


def test_reconcile_fails_running_task_without_lease():
    task = make_task(TaskStatus.RUNNING, "running-orphan")

    repo = FakeRepository([task])
    state = FakeStateStore()

    manager = TaskManager(repository=repo, state_store=state)

    result = manager.reconcile_active_tasks()

    assert result["running_orphaned"] == 1
    assert task.status == TaskStatus.FAILED
    assert task.error_type == "worker_lost"
    assert task.completed_at is not None
    assert "lost its worker lease" in task.error
    assert "running-orphan" in state.released
    assert repo.updated == [task]


def test_reconcile_fails_running_task_with_expired_lease():
    task = make_task(TaskStatus.RUNNING, "running-expired")

    past = (
        datetime.now(timezone.utc) - timedelta(seconds=30)
    ).isoformat()

    repo = FakeRepository([task])
    state = FakeStateStore({
        "running-expired": {
            "task_id": "running-expired",
            "worker_id": "old-worker",
            "lease_expires_at": past,
        }
    })

    manager = TaskManager(repository=repo, state_store=state)

    result = manager.reconcile_active_tasks()

    assert result["running_orphaned"] == 1
    assert task.status == TaskStatus.FAILED
    assert task.error_type == "worker_lost"
    assert task.completed_at is not None
    assert "lease expired" in task.error
    assert "running-expired" in state.released
    assert repo.updated == [task]
