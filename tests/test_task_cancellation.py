import threading
import time

from dotenv import load_dotenv

load_dotenv('/opt/jarvis/.env')


def long_running_handler():
    time.sleep(30)

from app.core.tasks import TaskManager
from app.models.tool import ToolDefinition
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter


def test_router_cancellation():
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="test.long_running",
            description="Long-running cancellation test",
            handler=long_running_handler,
            timeout_seconds=30,
        )
    )

    manager = TaskManager()

    router = ToolRouter(
        registry=registry,
        task_manager=manager,
    )

    result_holder = {}

    def run_tool():
        result_holder["result"] = router.execute("test.long_running")

    worker = threading.Thread(target=run_tool)
    worker.start()

    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:
        tasks = manager.list()

        if tasks and tasks[-1].status.value == "running":
            break

        time.sleep(0.05)

    task = manager.list()[-1]

    assert task.status.value == "running"

    manager.request_cancel(task.task_id)

    worker.join(timeout=10)

    assert not worker.is_alive()

    result = result_holder["result"]

    assert result["ok"] is False
    assert result["error_type"] == "cancelled"
    assert result["task_id"] == task.task_id

    final_task = manager.get(task.task_id)

    assert final_task.status.value == "cancelled"
    assert final_task.cancel_requested is True

def test_cancel_all_active_tasks():
    from app.core.tasks import TaskManager
    from app.models.task import TaskStatus

    class FakeRepository:
        def __init__(self):
            self.tasks = {}
            self.updated = []

        def create(self, task):
            self.tasks[task.task_id] = task

        def list_active(self):
            return [
                task
                for task in self.tasks.values()
                if task.status in (
                    TaskStatus.QUEUED,
                    TaskStatus.RUNNING,
                )
            ]

        def update(self, task):
            self.tasks[task.task_id] = task
            self.updated.append(task)

    class FakeStateStore:
        def __init__(self):
            self.saved = []

        def save(self, task, worker_id=None):
            self.saved.append((task.task_id, task.status, worker_id))

        def release_lease(self, task_id):
            pass

        def acquire_lease(self, task_id, worker_id):
            return True

        def get_lease(self, task_id):
            return None

    repository = FakeRepository()
    state_store = FakeStateStore()

    manager = TaskManager(
        repository=repository,
        state_store=state_store,
    )

    queued = manager.create("test.queued")
    running = manager.create("test.running")

    manager.mark_running(running.task_id)

    cancelled = manager.cancel_all_active()

    assert cancelled == 2

    assert manager.get(queued.task_id).status == TaskStatus.CANCELLED
    assert manager.get(queued.task_id).cancel_requested is True

    running_task = manager.get(running.task_id)
    assert running_task.status == TaskStatus.RUNNING
    assert running_task.cancel_requested is True
