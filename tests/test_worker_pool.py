import threading
import time

from app.core.worker_pool import TaskWorkerPool, WorkItem


def test_worker_pool_limits_concurrency():
    active = 0
    max_active = 0
    lock = threading.Lock()
    started = threading.Event()
    release = threading.Event()

    def run_task(item):
        nonlocal active, max_active

        with lock:
            active += 1
            max_active = max(max_active, active)
            started.set()

        release.wait(timeout=5)

        with lock:
            active -= 1

    pool = TaskWorkerPool(
        run_task,
        max_workers=1,
        max_queue_size=4,
    )

    try:
        first = WorkItem(
            task_id="task-1",
            tool_name="test.tool",
            args={},
        )
        second = WorkItem(
            task_id="task-2",
            tool_name="test.tool",
            args={},
        )

        assert pool.submit(first) is True
        assert started.wait(timeout=2)

        assert pool.submit(second) is True

        # Give the worker a moment. With one worker, the second
        # task must still be waiting in the queue.
        time.sleep(0.2)

        assert max_active == 1
        assert pool.queue_size == 1

        release.set()

        deadline = time.time() + 5
        while pool.queue_size != 0 and time.time() < deadline:
            time.sleep(0.05)

        assert pool.queue_size == 0

    finally:
        release.set()
        pool.shutdown(wait=True)


def test_worker_pool_rejects_when_queue_is_full():
    started = threading.Event()
    release = threading.Event()

    def run_task(item):
        started.set()
        release.wait(timeout=5)

    pool = TaskWorkerPool(
        run_task,
        max_workers=1,
        max_queue_size=1,
    )

    try:
        assert pool.submit(
            WorkItem(
                task_id="task-1",
                tool_name="test.tool",
                args={},
            )
        ) is True

        assert started.wait(timeout=2)

        # One item can wait in the bounded queue.
        assert pool.submit(
            WorkItem(
                task_id="task-2",
                tool_name="test.tool",
                args={},
            )
        ) is True

        # The queue is now full.
        assert pool.submit(
            WorkItem(
                task_id="task-3",
                tool_name="test.tool",
                args={},
            )
        ) is False

    finally:
        release.set()
        pool.shutdown(wait=True)


def test_worker_pool_worker_survives_task_exception():
    calls = []
    second_started = threading.Event()

    def run_task(item):
        calls.append(item.task_id)

        if item.task_id == "task-1":
            raise RuntimeError("expected test failure")

        second_started.set()

    pool = TaskWorkerPool(
        run_task,
        max_workers=1,
        max_queue_size=2,
    )

    try:
        assert pool.submit(
            WorkItem(
                task_id="task-1",
                tool_name="test.tool",
                args={},
            )
        ) is True

        assert pool.submit(
            WorkItem(
                task_id="task-2",
                tool_name="test.tool",
                args={},
            )
        ) is True

        assert second_started.wait(timeout=2)
        assert calls == ["task-1", "task-2"]

    finally:
        pool.shutdown(wait=True)


def test_worker_pool_can_skip_cancelled_queued_work():
    executed = []
    first_started = threading.Event()
    release_first = threading.Event()

    cancelled = {"task-2": True}

    def run_task(item):
        # Simulate the same guard used by the router's task callback.
        if cancelled.get(item.task_id, False):
            return

        executed.append(item.task_id)

        if item.task_id == "task-1":
            first_started.set()
            release_first.wait(timeout=5)

    pool = TaskWorkerPool(
        run_task,
        max_workers=1,
        max_queue_size=2,
    )

    try:
        assert pool.submit(
            WorkItem(
                task_id="task-1",
                tool_name="test.tool",
                args={},
            )
        ) is True

        assert first_started.wait(timeout=2)

        # Task 2 is cancelled while waiting in the queue.
        assert pool.submit(
            WorkItem(
                task_id="task-2",
                tool_name="test.tool",
                args={},
            )
        ) is True

        assert pool.queue_size == 1

        release_first.set()

        deadline = time.time() + 5
        while pool.queue_size != 0 and time.time() < deadline:
            time.sleep(0.05)

        assert pool.queue_size == 0
        assert executed == ["task-1"]

    finally:
        release_first.set()
        pool.shutdown(wait=True)
