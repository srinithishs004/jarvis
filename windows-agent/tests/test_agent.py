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
    assert message["registration"]["capabilities"] == {
        "capabilities": [
            "system.info",
            "app.list",
            "app.launch",
            "app.close",
            "window.focus",
            "keyboard.type",
            "keyboard.press",
            "mouse.move",
            "mouse.click",
            "clipboard.read",
            "clipboard.write",
            "filesystem.read",
            "filesystem.list",
            "filesystem.write",
        ],
        "tool_names": [
            "windows.system.info",
            "windows.app.list",
            "windows.app.launch",
            "windows.app.close",
            "windows.window.focus",
            "windows.keyboard.type",
            "windows.keyboard.press",
            "windows.mouse.move",
            "windows.mouse.click",
            "windows.clipboard.read",
            "windows.clipboard.write",
            "windows.filesystem.read",
            "windows.filesystem.list",
            "windows.filesystem.write",
        ],
    }


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

    def read_file(self, path):
        self.calls.append(("read_file", path))
        return {"path": path, "text": "hello"}

    def list_directory(self, path):
        self.calls.append(("list_directory", path))
        return {"path": path, "entries": []}

    def write_file(self, path, text):
        self.calls.append(("write_file", path, text))
        return {"path": path, "written": True}


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


def test_filesystem_read_delegates_to_operations():
    operations = FakeWindowsOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.filesystem.read",
        {"path": "notes.txt"},
    )

    assert result == {"path": "notes.txt", "text": "hello"}
    assert operations.calls == [("read_file", "notes.txt")]


def test_filesystem_list_delegates_to_operations():
    operations = FakeWindowsOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.filesystem.list",
        {"path": "docs"},
    )

    assert result == {"path": "docs", "entries": []}
    assert operations.calls == [("list_directory", "docs")]


def test_filesystem_write_delegates_to_operations():
    operations = FakeWindowsOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.filesystem.write",
        {"path": "notes.txt", "text": "hello"},
    )

    assert result == {"path": "notes.txt", "written": True}
    assert operations.calls == [("write_file", "notes.txt", "hello")]




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
        "keyboard.type",
        "keyboard.press",
        "mouse.move",
        "mouse.click",
        "clipboard.read",
        "clipboard.write",
        "filesystem.read",
        "filesystem.list",
        "filesystem.write",
    ]

    assert capabilities["tool_names"] == [
        "windows.system.info",
        "windows.app.list",
        "windows.app.launch",
        "windows.app.close",
        "windows.window.focus",
        "windows.keyboard.type",
        "windows.keyboard.press",
        "windows.mouse.move",
        "windows.mouse.click",
        "windows.clipboard.read",
        "windows.clipboard.write",
        "windows.filesystem.read",
        "windows.filesystem.list",
        "windows.filesystem.write",
    ]


class InputOperations:
    def __init__(self):
        self.calls = []

    def list_applications(self):
        return []

    def launch_application(self, application):
        return {"application": application}

    def close_window(self, window_id):
        return {"window_id": window_id}

    def focus_window(self, window_id):
        return {"window_id": window_id}

    def type_text(self, text):
        self.calls.append(("type_text", text))
        return {"typed": text}

    def press_key(self, key):
        self.calls.append(("press_key", key))
        return {"pressed": key}

    def move_mouse(self, x, y):
        self.calls.append(("move_mouse", x, y))
        return {"x": x, "y": y}

    def click_mouse(self, x, y, button):
        self.calls.append(("click_mouse", x, y, button))
        return {"x": x, "y": y, "button": button}

    def read_clipboard(self):
        self.calls.append(("read_clipboard",))
        return {"text": "clipboard text"}

    def write_clipboard(self, text):
        self.calls.append(("write_clipboard", text))
        return {"written": text}

    def read_file(self, path):
        self.calls.append(("read_file", path))
        return {"path": path}

    def list_directory(self, path):
        self.calls.append(("list_directory", path))
        return {"path": path}

    def write_file(self, path, text):
        self.calls.append(("write_file", path, text))
        return {"path": path, "text": text}


def test_keyboard_type_delegates_to_operations():
    operations = InputOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.keyboard.type",
        {"text": "hello"},
    )

    assert result == {"typed": "hello"}
    assert operations.calls == [("type_text", "hello")]


def test_keyboard_press_delegates_to_operations():
    operations = InputOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.keyboard.press",
        {"key": "ENTER"},
    )

    assert result == {"pressed": "ENTER"}
    assert operations.calls == [("press_key", "ENTER")]


def test_mouse_move_delegates_to_operations():
    operations = InputOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.mouse.move",
        {"x": 100, "y": 200},
    )

    assert result == {"x": 100, "y": 200}
    assert operations.calls == [("move_mouse", 100, 200)]


def test_mouse_click_delegates_to_operations():
    operations = InputOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.mouse.click",
        {"x": 100, "y": 200, "button": "left"},
    )

    assert result == {"x": 100, "y": 200, "button": "left"}
    assert operations.calls == [("click_mouse", 100, 200, "left")]


def test_clipboard_read_delegates_to_operations():
    operations = InputOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.clipboard.read",
        {},
    )

    assert result == {"text": "clipboard text"}
    assert operations.calls == [("read_clipboard",)]


def test_clipboard_write_delegates_to_operations():
    operations = InputOperations()
    executor = CommandExecutor(operations=operations)

    result = executor.execute(
        "windows.clipboard.write",
        {"text": "hello clipboard"},
    )

    assert result == {"written": "hello clipboard"}
    assert operations.calls == [("write_clipboard", "hello clipboard")]


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("windows.keyboard.type", {}),
        ("windows.keyboard.type", {"text": ""}),
        ("windows.keyboard.type", {"text": 123}),
        ("windows.keyboard.type", {"text": "hello", "extra": True}),
        ("windows.keyboard.press", {}),
        ("windows.keyboard.press", {"key": ""}),
        ("windows.keyboard.press", {"key": 123}),
        ("windows.keyboard.press", {"key": "ENTER", "extra": True}),
        ("windows.mouse.move", {"x": -1, "y": 0}),
        ("windows.mouse.move", {"x": 0, "y": -1}),
        ("windows.mouse.move", {"x": "10", "y": 20}),
        ("windows.mouse.move", {"x": True, "y": 20}),
        ("windows.mouse.move", {"x": 10}),
        ("windows.mouse.click", {"x": 0, "y": 0, "button": ""}),
        ("windows.mouse.click", {"x": 0, "y": 0, "button": 123}),
        ("windows.mouse.click", {"x": 0, "y": 0, "button": "left", "extra": True}),
        ("windows.mouse.click", {"x": -1, "y": 0, "button": "left"}),
        ("windows.clipboard.read", {"extra": True}),
        ("windows.clipboard.write", {}),
        ("windows.clipboard.write", {"text": ""}),
        ("windows.clipboard.write", {"text": 123}),
        ("windows.clipboard.write", {"text": "hello", "extra": True}),
    ],
)
def test_input_tools_reject_invalid_arguments(tool_name, arguments):
    executor = CommandExecutor(operations=InputOperations())

    with pytest.raises(ValueError):
        executor.execute(tool_name, arguments)
