from typing import Any

from app.models.task import Task
from app.redis.store import RedisStore


class TaskStateStore:
    PREFIX = "jarvis:task:"

    def __init__(self, redis: RedisStore | None = None) -> None:
        self.redis = redis or RedisStore()

    def _key(self, task_id: str) -> str:
        return f"{self.PREFIX}{task_id}"

    def save(self, task: Task, ttl_seconds: int = 86400) -> None:
        self.redis.set(
            self._key(task.task_id),
            {
                "task_id": task.task_id,
                "status": task.status.value,
                "cancel_requested": task.cancel_requested,
            },
            ttl_seconds=ttl_seconds,
        )

    def get(self, task_id: str) -> dict[str, Any] | None:
        return self.redis.get(self._key(task_id))

    def delete(self, task_id: str) -> None:
        self.redis.delete(self._key(task_id))

    def request_cancel(self, task_id: str) -> None:
        state = self.get(task_id) or {
            "task_id": task_id,
            "status": "unknown",
        }

        state["cancel_requested"] = True

        self.redis.set(
            self._key(task_id),
            state,
            ttl_seconds=86400,
        )
