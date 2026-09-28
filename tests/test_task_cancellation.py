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
