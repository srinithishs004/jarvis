from datetime import datetime, timezone

from app.db.tasks import TaskRepository
from app.models.task import Task, TaskStatus
from app.redis.task_state import TaskStateStore


class TaskManager:
    def __init__(
        self,
        repository: TaskRepository | None = None,
        state_store: TaskStateStore | None = None,
    ) -> None:
        self._tasks: dict[str, Task] = {}
        self._last_cancel_check: dict[str, datetime] = {}
        self.repository = repository or TaskRepository()
        self.state_store = state_store or TaskStateStore()

    def create(
        self,
        tool_name: str,
        arguments: dict | None = None,
        confirmation_id: str | None = None,
    ) -> Task:
        task = Task(
            tool_name=tool_name,
            arguments=arguments or {},
            confirmation_id=confirmation_id,
        )

        self._tasks[task.task_id] = task

        self.repository.create(task)
        self.state_store.save(task)

        return task

    def get(self, task_id: str) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"Task not found: {task_id}") from None

    def mark_running(self, task_id: str) -> Task:
        task = self.get(task_id)

        if task.status != TaskStatus.QUEUED:
            raise ValueError(
                f"Cannot start task in state: {task.status.value}"
            )

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        self.repository.update(task)
        self.state_store.save(task)

        return task

    def mark_succeeded(self, task_id: str, result=None) -> Task:
        task = self.get(task_id)

        if task.status != TaskStatus.RUNNING:
            raise ValueError(
                f"Cannot succeed task in state: {task.status.value}"
            )

        task.status = TaskStatus.SUCCEEDED
        task.result = result
        task.completed_at = datetime.now(timezone.utc)

        self.repository.update(task)
        self.state_store.save(task)

        return task

    def mark_failed(
        self,
        task_id: str,
        error: str,
        error_type: str = "execution_error",
    ) -> Task:
        task = self.get(task_id)

        if task.status != TaskStatus.RUNNING:
            raise ValueError(
                f"Cannot fail task in state: {task.status.value}"
            )

        task.status = TaskStatus.FAILED
        task.error = error
        task.error_type = error_type
        task.completed_at = datetime.now(timezone.utc)

        self.repository.update(task)
        self.state_store.save(task)

        return task

    def request_cancel(self, task_id: str) -> Task:
        task = self.get(task_id)

        if task.status in (
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ):
            raise ValueError(
                f"Cannot cancel completed task: {task.status.value}"
            )

        task.cancel_requested = True

        if task.status == TaskStatus.QUEUED:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)

        self.repository.update(task)
        self.state_store.save(task)

        return task

    def mark_cancelled(self, task_id: str) -> Task:
        task = self.get(task_id)

        if task.status != TaskStatus.RUNNING:
            raise ValueError(
                f"Cannot cancel task in state: {task.status.value}"
            )

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)

        self.repository.update(task)
        self.state_store.save(task)

        return task

    def is_cancel_requested(
        self,
        task_id: str,
        redis_check_interval: float = 1.0,
    ) -> bool:
        task = self.get(task_id)

        if task.cancel_requested:
            return True

        now = datetime.now(timezone.utc)
        last_check = self._last_cancel_check.get(task_id)

        if (
            last_check is not None
            and (now - last_check).total_seconds() < redis_check_interval
        ):
            return False

        self._last_cancel_check[task_id] = now

        state = self.state_store.get(task_id)

        if state is None:
            return False

        if state.get("cancel_requested", False):
            task.cancel_requested = True
            return True

        return False

    def list(self) -> list[Task]:
        return list(self._tasks.values())