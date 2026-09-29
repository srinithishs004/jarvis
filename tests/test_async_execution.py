import time

from dotenv import load_dotenv

load_dotenv("/opt/jarvis/.env")

from app.models.tool import ToolDefinition, PermissionLevel
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter
from app.core.tasks import TaskManager, TaskStatus


def long_running_handler(**kwargs):
    time.sleep(30)
    return {"finished": True}


def test_async_execution_can_be_cancelled():
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="test.async-long",
            description="Long-running async lifecycle test",
            permission_level=PermissionLevel.L0,
            handler=long_running_handler,
        )
    )

    manager = TaskManager()
    router = ToolRouter(
        registry=registry,
        task_manager=manager,
    )

    # Keep this test focused on execution rather than audit persistence.
    router._audit = lambda *args, **kwargs: None

    result = router.execute_background("test.async-long", arguments={})

    assert result["ok"] is True
    assert result["status"] in {"queued", "running"}

    task_id = result["task_id"]

    # Confirm the task actually reached RUNNING.
    deadline = time.time() + 5
    task = manager.get(task_id)

    while task.status != TaskStatus.RUNNING and time.time() < deadline:
        time.sleep(0.05)
        task = manager.get(task_id)

    assert task.status == TaskStatus.RUNNING

    # The worker should have acquired a lease.
    lease_deadline = time.time() + 5
    lease = None

    while time.time() < lease_deadline:
        lease = manager.state_store.get_lease(task_id)

        if lease is not None:
            break

        time.sleep(0.05)

    assert lease is not None
    assert lease["task_id"] == task_id
    assert lease["worker_id"] == manager.worker_id
    # Request cancellation.
    manager.request_cancel(task_id)

    # Wait for the worker to observe cancellation and terminate.
    deadline = time.time() + 10

    while time.time() < deadline:
        task = manager.get(task_id)
        if task.status == TaskStatus.CANCELLED:
            break
        time.sleep(0.1)

    assert task.status == TaskStatus.CANCELLED
    assert task.cancel_requested is True

    # Terminal task must release its worker lease.
    assert manager.state_store.get_lease(task_id) is None
