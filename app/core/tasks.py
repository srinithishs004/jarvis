from datetime import datetime, timezone
from uuid import uuid4

from app.db.tasks import TaskRepository
from app.models.task import Task, TaskStatus
from app.redis.task_state import TaskStateStore


class TaskManager:
    def __init__(
        self,
        repository: TaskRepository | None = None,
        state_store: TaskStateStore | None = None,
    ) -> None:
        self.worker_id = str(uuid4())
        self._tasks: dict[str, Task] = {}
        self._last_cancel_check: dict[str, datetime] = {}
        self._last_heartbeat: dict[str, datetime] = {}
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
        task = self._tasks.get(task_id)

        if task is not None:
            return task

        task = self.repository.get(task_id)

        if task is None:
            raise KeyError(f"Task not found: {task_id}")

        self._tasks[task_id] = task
        return task

    def mark_running(self, task_id: str) -> Task:
        task = self.get(task_id)

        if task.status != TaskStatus.QUEUED:
            raise ValueError(
                f"Cannot start task in state: {task.status.value}"
            )

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        self.repository.update(task)
        self.state_store.save(
            task,
            worker_id=self.worker_id,
        )
        self.state_store.acquire_lease(
            task.task_id,
            self.worker_id,
        )
        self._last_heartbeat[task.task_id] = datetime.now(timezone.utc)

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

        self.state_store.release_lease(task.task_id)
        self.repository.update(task)
        self.state_store.save(task)
        self._last_heartbeat.pop(task.task_id, None)

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

        self.state_store.release_lease(task.task_id)
        self.repository.update(task)
        self.state_store.save(task)
        self._last_heartbeat.pop(task.task_id, None)

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

        self.state_store.release_lease(task.task_id)
        self.repository.update(task)
        self.state_store.save(task)
        self._last_heartbeat.pop(task.task_id, None)

        return task

    def heartbeat(
        self,
        task_id: str,
        heartbeat_interval: float = 5.0,
    ) -> bool:
        task = self.get(task_id)

        if task.status != TaskStatus.RUNNING:
            return False

        now = datetime.now(timezone.utc)
        last_heartbeat = self._last_heartbeat.get(task_id)

        if (
            last_heartbeat is not None
            and (now - last_heartbeat).total_seconds() < heartbeat_interval
        ):
            return True

        self.state_store.renew_lease(
            task_id,
            self.worker_id,
        )

        self._last_heartbeat[task_id] = now
        return True

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

    def reconcile_active_tasks(self) -> dict[str, int]:
        """Reconcile persisted queued/running tasks after process startup."""
        active_tasks = self.repository.list_active()

        summary = {
            "checked": 0,
            "queued": 0,
            "running_active": 0,
            "running_orphaned": 0,
        }

        now = datetime.now(timezone.utc)

        for task in active_tasks:
            summary["checked"] += 1
            self._tasks[task.task_id] = task

            if task.status == TaskStatus.QUEUED:
                summary["queued"] += 1
                continue

            if task.status != TaskStatus.RUNNING:
                continue

            lease = self.state_store.get_lease(task.task_id)

            if lease is None:
                task.status = TaskStatus.FAILED
                task.error = (
                    "Task lost its worker lease during process recovery"
                )
                task.error_type = "worker_lost"
                task.completed_at = now

                self.repository.update(task)
                self.state_store.save(task)
                self.state_store.release_lease(task.task_id)

                summary["running_orphaned"] += 1
                continue

            expires_at_raw = lease.get("lease_expires_at")

            if expires_at_raw:
                try:
                    expires_at = datetime.fromisoformat(expires_at_raw)

                    if expires_at <= now:
                        task.status = TaskStatus.FAILED
                        task.error = (
                            "Task worker lease expired during "
                            "process recovery"
                        )
                        task.error_type = "worker_lost"
                        task.completed_at = now

                        self.repository.update(task)
                        self.state_store.save(task)
                        self.state_store.release_lease(task.task_id)

                        summary["running_orphaned"] += 1
                        continue

                except (TypeError, ValueError):
                    # Invalid lease metadata is not safe enough to
                    # claim ownership from another worker.
                    summary["running_active"] += 1
                    continue

            summary["running_active"] += 1

        return summary

    def list(self) -> list[Task]:
        return list(self._tasks.values())