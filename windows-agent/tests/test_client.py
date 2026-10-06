import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from jarvis_agent.client import JarvisAgentClient
from jarvis_agent.config import AgentConfig
from jarvis_agent.executor import CommandExecutor


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []

    async def send(self, message):
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            raise StopAsyncIteration
        return self.messages.pop(0)


def make_client():
    config = AgentConfig(
        server_url="ws://localhost:8000/ws/devices",
        device_id="windows-test",
        device_name="Test PC",
        auth_secret="test-secret",
        heartbeat_interval_seconds=999,
    )

    return JarvisAgentClient(
        config,
        CommandExecutor(),
    )


def test_client_executes_allowlisted_command():
    client = make_client()

    websocket = FakeWebSocket([
        json.dumps({
            "type": "command",
            "request_id": "req-1",
            "tool_name": "windows.system.info",
            "arguments": {},
        }),
    ])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-1",
                "tool_name": "windows.system.info",
                "arguments": {},
            }),
        )
    )

    assert len(websocket.sent) == 1

    result = websocket.sent[0]

    assert result["type"] == "command_result"
    assert result["request_id"] == "req-1"
    assert result["success"] is True
    assert isinstance(result["result"], dict)
    assert "hostname" in result["result"]


def test_client_rejects_unknown_command():
    client = make_client()

    websocket = FakeWebSocket([])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-2",
                "tool_name": "windows.arbitrary_command",
                "arguments": {},
            }),
        )
    )

    assert len(websocket.sent) == 1

    result = websocket.sent[0]

    assert result["type"] == "command_result"
    assert result["request_id"] == "req-2"
    assert result["success"] is False
    assert "Unsupported agent tool" in result["error"]


def test_client_rejects_malformed_command():
    client = make_client()

    websocket = FakeWebSocket([])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-3",
                "tool_name": "windows.system.info",
                "arguments": "not-a-dict",
            }),
        )
    )

    assert websocket.sent == []


class FakeOperations:
    def list_applications(self):
        return [{"window_id": "win-1", "title": "Notepad"}]

    def launch_application(self, application):
        return {"application": application, "launched": True}

    def close_window(self, window_id):
        return {"window_id": window_id, "closed": True}

    def focus_window(self, window_id):
        return {"window_id": window_id, "focused": True}


def make_client_with_fake_operations():
    config = AgentConfig(
        server_url="ws://localhost:8000/ws/devices",
        device_id="windows-test",
        device_name="Test PC",
        auth_secret="test-secret",
        heartbeat_interval_seconds=999,
    )

    return JarvisAgentClient(
        config,
        CommandExecutor(operations=FakeOperations()),
    )


def test_client_executes_app_list_command():
    client = make_client_with_fake_operations()
    websocket = FakeWebSocket([])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-list",
                "tool_name": "windows.app.list",
                "arguments": {},
            }),
        )
    )

    assert websocket.sent == [{
        "type": "command_result",
        "request_id": "req-list",
        "success": True,
        "result": [{"window_id": "win-1", "title": "Notepad"}],
        "error": None,
    }]


def test_client_executes_app_launch_command():
    client = make_client_with_fake_operations()
    websocket = FakeWebSocket([])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-launch",
                "tool_name": "windows.app.launch",
                "arguments": {"application": "notepad.exe"},
            }),
        )
    )

    assert websocket.sent[0]["success"] is True
    assert websocket.sent[0]["request_id"] == "req-launch"
    assert websocket.sent[0]["result"] == {
        "application": "notepad.exe",
        "launched": True,
    }


def test_client_executes_app_close_command():
    client = make_client_with_fake_operations()
    websocket = FakeWebSocket([])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-close",
                "tool_name": "windows.app.close",
                "arguments": {"window_id": "win-1"},
            }),
        )
    )

    assert websocket.sent[0]["success"] is True
    assert websocket.sent[0]["request_id"] == "req-close"
    assert websocket.sent[0]["result"] == {
        "window_id": "win-1",
        "closed": True,
    }


def test_client_executes_window_focus_command():
    client = make_client_with_fake_operations()
    websocket = FakeWebSocket([])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-focus",
                "tool_name": "windows.window.focus",
                "arguments": {"window_id": "win-1"},
            }),
        )
    )

    assert websocket.sent[0]["success"] is True
    assert websocket.sent[0]["request_id"] == "req-focus"
    assert websocket.sent[0]["result"] == {
        "window_id": "win-1",
        "focused": True,
    }


class FailingOperations:
    def list_applications(self):
        raise RuntimeError("Windows API failure")


def test_client_returns_structured_error_for_operation_failure():
    config = AgentConfig(
        server_url="ws://localhost:8000/ws/devices",
        device_id="windows-test",
        device_name="Test PC",
        auth_secret="test-secret",
        heartbeat_interval_seconds=999,
    )

    client = JarvisAgentClient(
        config,
        CommandExecutor(operations=FailingOperations()),
    )

    websocket = FakeWebSocket([])

    asyncio.run(
        client._handle_message(
            websocket,
            json.dumps({
                "type": "command",
                "request_id": "req-fail",
                "tool_name": "windows.app.list",
                "arguments": {},
            }),
        )
    )

    assert websocket.sent == [{
        "type": "command_result",
        "request_id": "req-fail",
        "success": False,
        "result": None,
        "error": "Windows API failure",
    }]
