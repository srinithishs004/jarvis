from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkItem:
    task_id: str
    tool_name: str
    args: dict[str, Any]
    confirmation_id: str | None = None


class TaskWorkerPool:
    def __init__(
        self,
        run_task: Callable[[WorkItem], None],
        *,
        max_workers: int = 2,
        max_queue_size: int = 16,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be >= 1")

        self._run_task = run_task
        self._max_workers = max_workers
        self._queue: queue.Queue[WorkItem | None] = queue.Queue(
            maxsize=max_queue_size
        )

        self._threads: list[threading.Thread] = []
        self._started = False
        self._stopping = False
        self._lock = threading.Lock()

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return

            self._stopping = False
            self._started = True

            for index in range(self._max_workers):
                thread = threading.Thread(
                    target=self._worker_loop,
                    name=f"jarvis-task-worker-{index + 1}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)

    def submit(self, item: WorkItem) -> bool:
        self.start()

        with self._lock:
            if self._stopping:
                return False

        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            return False

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if not self._started or self._stopping:
                return

            self._stopping = True
            threads = list(self._threads)

        for _ in threads:
            self._queue.put(None)

        if wait:
            for thread in threads:
                thread.join(timeout=5)

        with self._lock:
            self._threads.clear()
            self._started = False

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()

            try:
                if item is None:
                    return

                try:
                    self._run_task(item)
                except Exception:
                    # Task execution is responsible for recording its own
                    # terminal state. Never allow one worker to die silently.
                    pass
            finally:
                self._queue.task_done()