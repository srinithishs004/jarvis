from __future__ import annotations

import asyncio

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.confirmation import ConfirmationManager
from app.core.orchestrator import Orchestrator
from app.core.tasks import TaskManager
from app.models.provider import ModelResponse
from app.models.tool import PermissionLevel, ToolDefinition
from app.providers.router import ModelRouter
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter


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
            if task.status.value in {"queued", "running"}
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
        return None

    def activate_kill_switch(self):
        self.kill_switch = True

    def deactivate_kill_switch(self):
        self.kill_switch = False

    def is_kill_switch_active(self):
        return self.kill_switch


class FakeProvider:
    name = "test-provider"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("FakeProvider has no response remaining")

        return ModelResponse(
            provider=self.name,
            model="test-model",
            content=self.responses.pop(0),
        )


def integration_health_handler():
    return {"status": "healthy", "service": "integration-test"}


def make_tool_router(*tools):
    registry = ToolRegistry()

    for tool in tools:
        registry.register(tool)

    manager = TaskManager(
        repository=FakeRepository(),
        state_store=FakeStateStore(),
    )

    router = ToolRouter(
        registry=registry,
        task_manager=manager,
        confirmation_manager=ConfirmationManager(),
        audit_repository=FakeAuditRepository(),
    )

    return registry, router, manager


def make_model_router(provider):
    from app.providers.registry import ModelProviderRegistry
    from app.providers.router import ModelRoute

    registry = ModelProviderRegistry()
    registry.register(provider)

    return ModelRouter(
        registry=registry,
        routes=[
            ModelRoute(
                name="test",
                provider=provider.name,
                model="test-model",
            )
        ],
        default_route="test",
    )


@pytest.fixture
def api_setup(monkeypatch):
    registry, tool_router, task_manager = make_tool_router(
        ToolDefinition(
            name="test.health",
            description="Integration test health tool",
            permission=PermissionLevel.L0,
            handler=integration_health_handler,
        )
    )

    provider = FakeProvider([])
    model_router = make_model_router(provider)

    orchestrator = Orchestrator(
        model_router=model_router,
        tool_registry=registry,
        tool_router=tool_router,
    )

    monkeypatch.setattr(main, "orchestrator", orchestrator)
    monkeypatch.setattr(main, "tool_registry", registry)
    monkeypatch.setattr(main, "tool_router", tool_router)

    return provider, tool_router, task_manager


def test_chat_responds_through_real_orchestrator(api_setup):
    provider, _, _ = api_setup

    provider.responses.append(
        '{"type":"respond","content":"JARVIS online."}'
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={"message": "Say hello"},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert body["decision"]["type"] == "respond"
    assert body["message"] == "JARVIS online."
    assert "execution" not in body


def test_chat_tool_call_executes_through_tool_router(api_setup):
    provider, _, _ = api_setup

    provider.responses.append(
        '{"type":"tool_call","tool_call":{"tool_name":"test.health","arguments":{}}}'
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={"message": "Check the test system"},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert body["decision"]["type"] == "tool_call"
    assert body["execution"]["ok"] is True
    assert body["execution"]["result"] == {
        "status": "healthy",
        "service": "integration-test",
    }
    assert body["message"] == "Done."


def test_chat_response_mode_reaches_response_engine(api_setup):
    provider, _, _ = api_setup

    provider.responses.append(
        '{"type":"tool_call","tool_call":{"tool_name":"test.health","arguments":{}}}'
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "Check the test system",
                "response_mode": "detailed",
            },
        )

    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert "Completed successfully." in body["message"]
    assert "Tool: test.health." in body["message"]


def test_chat_confirmation_required_does_not_execute(api_setup):
    executed = []

    def dangerous_handler():
        executed.append(True)
        return {"dangerous": True}

    registry, tool_router, task_manager = make_tool_router(
        ToolDefinition(
            name="test.dangerous",
            description="Confirmation-required integration tool",
            permission=PermissionLevel.L2,
            handler=dangerous_handler,
        )
    )

    provider = FakeProvider(
        [
            '{"type":"tool_call","tool_call":{"tool_name":"test.dangerous","arguments":{}}}'
        ]
    )

    orchestrator = Orchestrator(
        model_router=make_model_router(provider),
        tool_registry=registry,
        tool_router=tool_router,
    )

    main.orchestrator = orchestrator
    main.tool_registry = registry
    main.tool_router = tool_router

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={"message": "Run the dangerous test action"},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is False
    assert body["execution"]["error_type"] == "confirmation_required"
    assert body["execution"]["requires_confirmation"] is True
    assert body["message"] == "Confirmation required."
    assert executed == []


def test_chat_unknown_tool_is_rejected(api_setup):
    provider, _, _ = api_setup

    provider.responses.append(
        '{"type":"tool_call","tool_call":{"tool_name":"test.does_not_exist","arguments":{}}}'
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={"message": "Use the missing tool"},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is False
    assert body["execution"]["error_type"] == "tool_not_found"
    assert body["message"] == "I couldn't find that tool."


def test_chat_malformed_model_output_is_rejected(api_setup):
    provider, _, _ = api_setup
    provider.responses.append("this is not valid JARVIS decision JSON")

    with pytest.raises(
        ValueError,
        match="Model returned invalid agent decision JSON",
    ):
        with TestClient(main.app) as client:
            client.post(
                "/chat",
                json={"message": "Do something"},
            )


def test_chat_kill_switch_blocks_tool_execution(api_setup):
    provider, _, task_manager = api_setup

    provider.responses.append(
        '{"type":"tool_call","tool_call":{"tool_name":"test.health","arguments":{}}}'
    )

    task_manager.activate_kill_switch()

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={"message": "Check the test system"},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is False
    assert body["execution"]["error_type"] == "kill_switch_active"
    assert body["message"] == "JARVIS kill switch is active."


def test_chat_silent_response_mode_returns_empty_message(api_setup):
    provider, _, _ = api_setup

    provider.responses.append(
        '{"type":"respond","content":"This should not be spoken."}'
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "Respond silently",
                "response_mode": "silent",
            },
        )

    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert body["message"] == ""


def test_chat_reuses_session_context(api_setup):
    provider, _, _ = api_setup

    provider.responses.extend(
        [
            '{"type":"respond","content":"First answer."}',
            '{"type":"respond","content":"Second answer."}',
        ]
    )

    with TestClient(main.app) as client:
        first = client.post(
            "/chat",
            json={"message": "Remember that my project is JARVIS."},
        )

        assert first.status_code == 200
        session_id = first.json()["session_id"]

        second = client.post(
            "/chat",
            json={
                "session_id": session_id,
                "message": "What project did I mention?",
            },
        )

    assert second.status_code == 200
    assert second.json()["session_id"] == session_id

    assert len(provider.requests) == 2

    second_messages = provider.requests[1].messages

    assert second_messages[1].role == "user"
    assert second_messages[1].content == (
        "Remember that my project is JARVIS."
    )
    assert second_messages[2].role == "assistant"
    assert second_messages[2].content == "First answer."
    assert second_messages[3].role == "user"
    assert second_messages[3].content == "What project did I mention?"


def test_backup_export_returns_validated_backup(api_setup, monkeypatch):
    from app.models.backup import (
        BackupManifest,
        BackupRecord,
        JarvisBackup,
        RedisBackupEntry,
    )

    backup = JarvisBackup(
        manifest=BackupManifest(
            postgres={"tasks": 1},
            redis={"entries": 1},
        ),
        postgres=[
            BackupRecord(
                table="tasks",
                row={"id": "task-1", "status": "succeeded"},
            )
        ],
        redis=[
            RedisBackupEntry(
                key="jarvis:session:session-1",
                value={"messages": []},
            )
        ],
    )

    class FakeBackupService:
        def create_backup(self):
            return backup

    monkeypatch.setattr(
        main,
        "backup_service",
        FakeBackupService(),
    )

    with TestClient(main.app) as client:
        response = client.post("/backup/export")

    assert response.status_code == 200

    body = response.json()

    assert body["ok"] is True
    assert body["backup"]["manifest"]["format_version"] == 1
    assert body["backup"]["postgres"] == [
        {
            "table": "tasks",
            "row": {
                "id": "task-1",
                "status": "succeeded",
            },
        }
    ]
    assert body["backup"]["redis"] == [
        {
            "key": "jarvis:session:session-1",
            "value": {"messages": []},
        }
    ]


def test_backup_restore_prepare_requires_valid_backup(monkeypatch):
    class FakeBackupService:
        def deserialize(self, payload):
            from app.backup.service import BackupError
            raise BackupError("Invalid JARVIS backup payload")

    monkeypatch.setattr(main, "backup_service", FakeBackupService())

    with TestClient(main.app) as client:
        response = client.post(
            "/backup/restore/prepare",
            json={"backup": "not-json"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["error_type"] == "invalid_backup"


def test_backup_restore_requires_confirmation(monkeypatch):
    from app.models.backup import BackupManifest, JarvisBackup

    backup = JarvisBackup(manifest=BackupManifest())

    class FakeBackupService:
        def deserialize(self, payload):
            return backup

        def serialize(self, value):
            return '{"valid":true}'

        def restore(self, value):
            raise AssertionError("restore must not execute before approval")

    monkeypatch.setattr(main, "backup_service", FakeBackupService())

    with TestClient(main.app) as client:
        response = client.post(
            "/backup/restore/prepare",
            json={"backup": '{"valid":true}'},
        )

        assert response.status_code == 200
        prepared = response.json()

        assert prepared["ok"] is True
        assert prepared["requires_confirmation"] is True
        confirmation_id = prepared["confirmation_id"]

        response = client.post(
            "/backup/restore",
            json={
                "backup": '{"valid":true}',
                "confirmation_id": confirmation_id,
            },
        )

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["error_type"] == "confirmation_required"


def test_backup_restore_confirmation_is_bound_to_payload(monkeypatch):
    from app.models.backup import BackupManifest, JarvisBackup

    backup = JarvisBackup(manifest=BackupManifest())

    restored = []

    class FakeBackupService:
        def deserialize(self, payload):
            return backup

        def serialize(self, value):
            return '{"valid":true}'

        def restore(self, value):
            restored.append(value)

    monkeypatch.setattr(main, "backup_service", FakeBackupService())

    with TestClient(main.app) as client:
        response = client.post(
            "/backup/restore/prepare",
            json={"backup": '{"valid":true}'},
        )

        assert response.status_code == 200
        confirmation_id = response.json()["confirmation_id"]

        response = client.post(
            "/confirmations/"
            f"{confirmation_id}/approve",
        )
        assert response.status_code == 200
        assert response.json()["approved"] is True

        response = client.post(
            "/backup/restore",
            json={
                "backup": '{"different":true}',
                "confirmation_id": confirmation_id,
            },
        )

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["error_type"] == "confirmation_required"
    assert restored == []


def test_backup_restore_succeeds_after_approval(monkeypatch):
    from app.models.backup import BackupManifest, JarvisBackup

    backup = JarvisBackup(manifest=BackupManifest())
    restored = []

    class FakeBackupService:
        def deserialize(self, payload):
            return backup

        def serialize(self, value):
            return '{"valid":true}'

        def restore(self, value):
            restored.append(value)

    monkeypatch.setattr(main, "backup_service", FakeBackupService())

    with TestClient(main.app) as client:
        response = client.post(
            "/backup/restore/prepare",
            json={"backup": '{"valid":true}'},
        )

        assert response.status_code == 200
        confirmation_id = response.json()["confirmation_id"]

        response = client.post(
            f"/confirmations/{confirmation_id}/approve",
        )
        assert response.status_code == 200
        assert response.json()["approved"] is True

        response = client.post(
            "/backup/restore",
            json={
                "backup": '{"valid":true}',
                "confirmation_id": confirmation_id,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["restored"] is True
    assert len(restored) == 1
    assert restored[0] is backup


def test_device_websocket_rejects_when_authentication_is_not_configured(
    monkeypatch,
):
    from app.devices.auth import DeviceAuthenticator

    class MissingSecretAuthenticator(DeviceAuthenticator):
        def __init__(self):
            raise ValueError("JARVIS_DEVICE_AUTH_SECRET must be configured")

    monkeypatch.setattr(
        main,
        "DeviceAuthenticator",
        MissingSecretAuthenticator,
    )

    with TestClient(main.app) as client:
        with client.websocket_connect("/ws/devices") as websocket:
            try:
                websocket.receive_json()
            except Exception:
                pass


def test_device_websocket_authenticated_connection(monkeypatch):
    from app.devices.auth import DeviceAuthenticator

    authenticator = DeviceAuthenticator("integration-test-secret")

    monkeypatch.setattr(
        main,
        "DeviceAuthenticator",
        lambda: authenticator,
    )

    with TestClient(main.app) as client:
        with client.websocket_connect("/ws/devices") as websocket:
            device_id = "windows-api-test"

            from app.models.device import (
                DeviceCapabilities,
                DeviceRegistration,
                DeviceType,
            )

            registration = DeviceRegistration(
                device_id=device_id,
                device_name="JARVIS Windows Test",
                device_type=DeviceType.WINDOWS,
                agent_version="test",
                capabilities=DeviceCapabilities(
                    capabilities=["keyboard"],
                    tool_names=["windows.keyboard"],
                ),
            )

            websocket.send_json(
                {
                    "type": "hello",
                    "registration": registration.model_dump(mode="json"),
                    "token": authenticator.create_token(device_id),
                }
            )

            response = websocket.receive_json()

            assert response == {
                "type": "ack",
                "request_type": "hello",
            }

            websocket.send_json(
                {
                    "type": "heartbeat",
                    "heartbeat": {
                        "device_id": device_id,
                    },
                }
            )

            response = websocket.receive_json()

            assert response == {
                "type": "ack",
                "request_type": "heartbeat",
            }

            assert main.device_connection_manager.connected(device_id)


def test_device_websocket_rejects_invalid_token(monkeypatch):
    from app.devices.auth import DeviceAuthenticator

    authenticator = DeviceAuthenticator("integration-test-secret")

    monkeypatch.setattr(
        main,
        "DeviceAuthenticator",
        lambda: authenticator,
    )

    with TestClient(main.app) as client:
        with client.websocket_connect("/ws/devices") as websocket:
            websocket.send_json(
                {
                    "type": "hello",
                    "registration": {
                        "device_id": "windows-invalid-auth",
                        "device_name": "Invalid Auth Test",
                        "device_type": "windows",
                        "agent_version": "test",
                        "capabilities": {
                            "capabilities": [],
                            "tool_names": [],
                        },
                    },
                    "token": "invalid-token",
                }
            )

            response = websocket.receive_json()

            assert response["type"] == "error"
            assert response["code"] == "authentication_failed"


def test_app_lifespan_starts_and_stops_device_monitor(monkeypatch):
    class FakeMonitor:
        instances = []

        def __init__(self, *args, **kwargs):
            self.started = False
            self.stopped = False
            self.run_calls = 0
            self.stop_event = asyncio.Event()
            FakeMonitor.instances.append(self)

        async def run(self):
            self.started = True
            self.run_calls += 1
            await self.stop_event.wait()

        def stop(self):
            self.stopped = True
            self.stop_event.set()

    monkeypatch.setattr(main, "DeviceLifecycleMonitor", FakeMonitor)

    with TestClient(main.app):
        assert len(FakeMonitor.instances) == 1
        monitor = FakeMonitor.instances[0]
        assert monitor.started is True
        assert monitor.run_calls == 1

    assert monitor.stopped is True
