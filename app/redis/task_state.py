from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.task import Task
from app.redis.store import RedisStore


class TaskStateStore:
    PREFIX = "jarvis:task:"
    LEASE_PREFIX = "jarvis:task-lease:"
    KILL_SWITCH_KEY = "jarvis:kill-switch"
    DEFAULT_TTL_SECONDS = 86400
    LEASE_TTL_SECONDS = 15

    def __init__(self, redis: RedisStore | None = None) -> None:
        self.redis = redis or RedisStore()

    def _key(self, task_id: str) -> str:
        return f"{self.PREFIX}{task_id}"

    def _lease_key(self, task_id: str) -> str:
        return f"{self.LEASE_PREFIX}{task_id}"

    def save(
        self,
        task: Task,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        worker_id: str | None = None,
    ) -> None:
        self.redis.set(
            self._key(task.task_id),
            {
                "task_id": task.task_id,
                "status": task.status.value,
                "cancel_requested": task.cancel_requested,
                "worker_id": worker_id,
            },
            ttl_seconds=ttl_seconds,
        )

    def get(self, task_id: str) -> dict[str, Any] | None:
        return self.redis.get(self._key(task_id))

    def delete(self, task_id: str) -> None:
        self.redis.delete(self._key(task_id))
        self.release_lease(task_id)

    def request_cancel(self, task_id: str) -> None:
        state = self.get(task_id) or {
            "task_id": task_id,
            "status": "unknown",
        }

        state["cancel_requested"] = True

        self.redis.set(
            self._key(task_id),
            state,
            ttl_seconds=self.DEFAULT_TTL_SECONDS,
        )

    def acquire_lease(
        self,
        task_id: str,
        worker_id: str,
        ttl_seconds: int = LEASE_TTL_SECONDS,
    ) -> None:
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=ttl_seconds)
        ).isoformat()

        self.redis.set(
            self._lease_key(task_id),
            {
                "task_id": task_id,
                "worker_id": worker_id,
                "lease_expires_at": expires_at,
            },
            ttl_seconds=ttl_seconds,
        )

    def renew_lease(
        self,
        task_id: str,
        worker_id: str,
        ttl_seconds: int = LEASE_TTL_SECONDS,
    ) -> None:
        lease = self.get_lease(task_id)

        if lease is None:
            self.acquire_lease(task_id, worker_id, ttl_seconds)
            return

        if lease.get("worker_id") != worker_id:
            raise RuntimeError(
                f"Task lease owned by another worker: {task_id}"
            )

        lease["lease_expires_at"] = (
            datetime.now(timezone.utc)
            + timedelta(seconds=ttl_seconds)
        ).isoformat()

        self.redis.set(
            self._lease_key(task_id),
            lease,
            ttl_seconds=ttl_seconds,
        )

    def get_lease(self, task_id: str) -> dict[str, Any] | None:
        return self.redis.get(self._lease_key(task_id))

    def release_lease(self, task_id: str) -> None:
        self.redis.delete(self._lease_key(task_id))

    def activate_kill_switch(self) -> None:
        self.redis.set(
            self.KILL_SWITCH_KEY,
            {"active": True},
        )

    def deactivate_kill_switch(self) -> None:
        self.redis.delete(self.KILL_SWITCH_KEY)

    def is_kill_switch_active(self) -> bool:
        state = self.redis.get(self.KILL_SWITCH_KEY)
        return bool(state and state.get("active", False))
