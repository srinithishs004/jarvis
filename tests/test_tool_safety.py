from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv("/opt/jarvis/.env")


from app.core.confirmation import ConfirmationManager
from app.core.permissions import PermissionEngine
from app.core.tasks import TaskManager
from app.models.tool import PermissionLevel, ToolDefinition
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter



def read_handler():
    return {"ok": True}


def important_handler():
    return {"ok": True}


def confirm_handler():
    return {"ok": True}


def dangerous_handler():
    return {"ok": True}


def noop_handler():
    return None


class FakeAuditRepository:
    def record(self, event):
        pass





class FakeRepository:
    def __init__(self):
        self.tasks = {}

    def create(self, task):
        self.tasks[task.task_id] = task

    def get(self, task_id):
        return self.tasks.get(task_id)

    def update(self, task):
        self.tasks[task.task_id] = task

    def list_active(self):
        return [
            task
            for task in self.tasks.values()
            if task.status.value in ("queued", "running")
        ]


class FakeStateStore:
    def __init__(self):
        self.tasks = {}
        self.kill_switch = False

    def save(self, task, worker_id=None):
        self.tasks[task.task_id] = {
            "task_id": task.task_id,
            "status": task.status.value,
            "cancel_requested": task.cancel_requested,
            "worker_id": worker_id,
        }

    def get(self, task_id):
        return self.tasks.get(task_id)

    def acquire_lease(self, task_id, worker_id, ttl_seconds=30):
        return True

    def release_lease(self, task_id):
        pass

    def renew_lease(self, task_id, worker_id, ttl_seconds=30):
        return True

    def get_lease(self, task_id):
        return {
            "task_id": task_id,
            "worker_id": "test-worker",
            "lease_expires_at": (
                datetime.now(timezone.utc) + timedelta(seconds=30)
            ).isoformat(),
        }

    def activate_kill_switch(self):
        self.kill_switch = True

    def deactivate_kill_switch(self):
        self.kill_switch = False

    def is_kill_switch_active(self):
        return self.kill_switch


def make_router(*tools):
    registry = ToolRegistry()

    for tool in tools:
        registry.register(tool)

    manager = TaskManager(
        repository=FakeRepository(),
        state_store=FakeStateStore(),
    )

    return ToolRouter(
        registry=registry,
        task_manager=manager,
        audit_repository=FakeAuditRepository(),
    ), manager


def test_l0_tool_executes_without_confirmation():
    calls = []

    router, _ = make_router(
        ToolDefinition(
            name="test.read",
            description="Read-only test tool",
            permission=PermissionLevel.L0,
            handler=read_handler,
        )
    )

    result = router.execute("test.read")

    assert result["ok"] is True


def test_l2_tool_requires_confirmation():
    calls = []

    router, _ = make_router(
        ToolDefinition(
            name="test.important",
            description="Important test tool",
            permission=PermissionLevel.L2,
            handler=read_handler,
        )
    )

    result = router.execute("test.important")

    assert result["ok"] is False
    assert result["error_type"] == "confirmation_required"
    assert result["requires_confirmation"] is True
    assert result["confirmation_id"]


def test_explicit_confirmation_requirement_is_enforced():
    calls = []

    router, _ = make_router(
        ToolDefinition(
            name="test.confirm",
            description="Explicit confirmation test tool",
            permission=PermissionLevel.L0,
            requires_confirmation=True,
            handler=read_handler,
        )
    )

    result = router.execute("test.confirm")

    assert result["ok"] is False
    assert result["error_type"] == "confirmation_required"


def test_confirmation_is_bound_to_tool_name():
    confirmations = ConfirmationManager()

    request = confirmations.create("test.tool_a")

    assert confirmations.approve(request.confirmation_id) is True
    assert confirmations.is_approved(
        request.confirmation_id,
        "test.tool_a",
    ) is True
    assert confirmations.is_approved(
        request.confirmation_id,
        "test.tool_b",
    ) is False


def test_approved_confirmation_allows_correct_tool():
    calls = []

    router, _ = make_router(
        ToolDefinition(
            name="test.important",
            description="Important test tool",
            permission=PermissionLevel.L2,
            handler=read_handler,
        )
    )

    first = router.execute("test.important")

    assert first["error_type"] == "confirmation_required"

    confirmation_id = first["confirmation_id"]

    assert router.confirmation_manager.approve(confirmation_id) is True

    second = router.execute(
        "test.important",
        confirmation_id=confirmation_id,
    )

    assert second["ok"] is True


def test_expired_confirmation_is_rejected():
    confirmations = ConfirmationManager(ttl_seconds=1)

    request = confirmations.create("test.tool")
    request.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    assert confirmations.approve(request.confirmation_id) is False
    assert confirmations.is_approved(
        request.confirmation_id,
        "test.tool",
    ) is False


def test_kill_switch_blocks_synchronous_execution():
    calls = []

    router, manager = make_router(
        ToolDefinition(
            name="test.read",
            description="Read-only test tool",
            permission=PermissionLevel.L0,
            handler=read_handler,
        )
    )

    manager.activate_kill_switch()

    result = router.execute("test.read")

    assert result["ok"] is False
    assert result["error_type"] == "kill_switch_active"


def test_kill_switch_blocks_background_execution():
    calls = []

    router, manager = make_router(
        ToolDefinition(
            name="test.read",
            description="Read-only test tool",
            permission=PermissionLevel.L0,
            handler=read_handler,
        )
    )

    manager.activate_kill_switch()

    result = router.execute_background("test.read")

    assert result["ok"] is False
    assert result["error_type"] == "kill_switch_active"


def test_unknown_tool_never_reaches_handler():
    router, _ = make_router()

    result = router.execute("test.does_not_exist")

    assert result["ok"] is False
    assert result["error_type"] == "tool_not_found"


def test_permission_check_precedes_handler_execution():
    calls = []

    router, _ = make_router(
        ToolDefinition(
            name="test.dangerous",
            description="Dangerous test tool",
            permission=PermissionLevel.L3,
            handler=read_handler,
        )
    )

    result = router.execute("test.dangerous")

    assert result["error_type"] == "confirmation_required"
    assert calls == []


def test_confirmation_context_is_bound():
    confirmations = ConfirmationManager()
    request = confirmations.create("backup.restore", context="backup-hash-a")

    assert confirmations.approve(request.confirmation_id) is True
    assert confirmations.is_approved(
        request.confirmation_id,
        "backup.restore",
        context="backup-hash-a",
    ) is True
    assert confirmations.is_approved(
        request.confirmation_id,
        "backup.restore",
        context="backup-hash-b",
    ) is False


def test_remote_tool_executes_through_remote_executor():
    from app.core.remote_executor import RemoteToolExecutor
    from app.models.capability import ExecutionLocation

    class FakeRemoteExecutor:
        def __init__(self):
            self.calls = []

        def run(
            self,
            *,
            tool_name,
            arguments,
            timeout_seconds,
            cancel_check=None,
            heartbeat=None,
        ):
            self.calls.append(
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "timeout_seconds": timeout_seconds,
                }
            )
            return "succeeded", {"hostname": "WIN-01"}

    remote = FakeRemoteExecutor()

    router, _ = make_router(
        ToolDefinition(
            name="windows.system.info",
            description="Read Windows system information",
            permission=PermissionLevel.L0,
            execution_location=ExecutionLocation.REMOTE,
            handler=None,
            input_schema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string"},
                },
                "required": ["device_id"],
                "additionalProperties": False,
            },
        )
    )

    router.remote_executor = remote

    result = router.execute(
        "windows.system.info",
        {"device_id": "windows-01"},
    )

    assert result["ok"] is True
    assert result["result"] == {"hostname": "WIN-01"}
    assert remote.calls == [
        {
            "tool_name": "windows.system.info",
            "arguments": {"device_id": "windows-01"},
            "timeout_seconds": 30.0,
        }
    ]
