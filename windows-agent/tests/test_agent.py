import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from jarvis_agent.auth import create_device_token
from jarvis_agent.config import AgentConfig
from jarvis_agent.executor import CommandExecutor
from jarvis_agent.protocol import (
    make_command_result,
    make_heartbeat,
    make_hello,
)


def test_create_device_token_is_deterministic():
    token1 = create_device_token("pc-01", "secret")
    token2 = create_device_token("pc-01", "secret")

    assert token1 == token2
    assert len(token1) == 64


def test_different_device_ids_have_different_tokens():
    token1 = create_device_token("pc-01", "secret")
    token2 = create_device_token("pc-02", "secret")

    assert token1 != token2


def test_hello_contains_windows_registration():
    message = make_hello(
        device_id="pc-01",
        device_name="My PC",
        agent_version="0.1.0",
        token="token",
    )

    assert message["type"] == "hello"
    assert message["token"] == "token"
    assert message["registration"]["device_id"] == "pc-01"
    assert message["registration"]["device_type"] == "windows"
    assert "windows.system.info" in (
        message["registration"]["capabilities"]["tool_names"]
    )


def test_heartbeat_contains_device_id():
    message = make_heartbeat("pc-01")

    assert message["type"] == "heartbeat"
    assert message["heartbeat"]["device_id"] == "pc-01"
    assert "timestamp" in message["heartbeat"]


def test_command_result_success():
    message = make_command_result(
        request_id="req-1",
        success=True,
        result={"hostname": "PC"},
    )

    assert message == {
        "type": "command_result",
        "request_id": "req-1",
        "success": True,
        "result": {"hostname": "PC"},
        "error": None,
    }


def test_executor_allows_system_info():
    executor = CommandExecutor()

    result = executor.execute(
        "windows.system.info",
        {},
    )

    assert isinstance(result, dict)
    assert "hostname" in result
    assert "system" in result


def test_executor_rejects_unknown_tools():
    executor = CommandExecutor()

    with pytest.raises(ValueError, match="Unsupported agent tool"):
        executor.execute(
            "windows.arbitrary_command",
            {},
        )


def test_executor_rejects_arguments_for_system_info():
    executor = CommandExecutor()

    with pytest.raises(
        ValueError,
        match="does not accept arguments",
    ):
        executor.execute(
            "windows.system.info",
            {"command": "whoami"},
        )


def test_config_requires_secrets(monkeypatch):
    for name in (
        "JARVIS_SERVER_URL",
        "JARVIS_DEVICE_ID",
        "JARVIS_DEVICE_NAME",
        "JARVIS_DEVICE_AUTH_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="Missing required"):
        AgentConfig.from_environment()


class FakeWindowsOperations:
    def __init__(self):
        self.calls = []

    def list_applications(self):
        self.calls.append(("list_applications",))
        return [{"window_id": "win-1", "title": "Notepad"}]

    def launch_application(self, application):
        self.calls.append(("launch_application", application))
        return {"application": application, "launched": True}

    def close_window(self, window_id):
        self.calls.append(("close_window", window_id))
        return {"window_id": window_id, "closed": True}

    def focus_window(self, window_id):
        self.calls.append(("focus_window", window_id))
        return {"window_id": window_id, "focused": True}


def test_executor_allows_app_list():
    operations = FakeWindowsOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute("windows.app.list", {})

    assert result == [{"window_id": "win-1", "title": "Notepad"}]
    assert operations.calls == [("list_applications",)]


def test_executor_allows_app_launch():
    operations = FakeWindowsOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.app.launch",
        {"application": "notepad.exe"},
    )

    assert result == {
        "application": "notepad.exe",
        "launched": True,
    }
    assert operations.calls == [
        ("launch_application", "notepad.exe"),
    ]


def test_executor_allows_app_close():
    operations = FakeWindowsOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.app.close",
        {"window_id": "win-1"},
    )

    assert result == {
        "window_id": "win-1",
        "closed": True,
    }
    assert operations.calls == [
        ("close_window", "win-1"),
    ]


def test_executor_allows_window_focus():
    operations = FakeWindowsOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.window.focus",
        {"window_id": "win-1"},
    )

    assert result == {
        "window_id": "win-1",
        "focused": True,
    }
    assert operations.calls == [
        ("focus_window", "win-1"),
    ]


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("windows.app.list", {"unexpected": True}),
        ("windows.app.launch", {}),
        ("windows.app.launch", {"application": 123}),
        ("windows.app.launch", {"application": "notepad.exe", "extra": True}),
        ("windows.app.close", {}),
        ("windows.app.close", {"window_id": 123}),
        ("windows.app.close", {"window_id": "win-1", "extra": True}),
        ("windows.window.focus", {}),
        ("windows.window.focus", {"window_id": 123}),
        ("windows.window.focus", {"window_id": "win-1", "extra": True}),
    ],
)
def test_executor_rejects_invalid_tool_arguments(
    tool_name,
    arguments,
):
    executor = CommandExecutor(operations=FakeWindowsOperations())

    with pytest.raises(ValueError, match="Invalid arguments"):
        executor.execute(tool_name, arguments)


def test_hello_advertises_all_allowlisted_windows_tools():
    message = make_hello(
        device_id="pc-01",
        device_name="My PC",
        agent_version="0.1.0",
        token="token",
    )

    capabilities = message["registration"]["capabilities"]

    assert capabilities["capabilities"] == [
        "system.info",
        "app.list",
        "app.launch",
        "app.close",
        "window.focus",
    ]

    assert capabilities["tool_names"] == [
        "windows.system.info",
        "windows.app.list",
        "windows.app.launch",
        "windows.app.close",
        "windows.window.focus",
    ]
