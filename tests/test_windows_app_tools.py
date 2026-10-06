from app.devices.tools import (
    make_windows_app_close_tool,
    make_windows_app_launch_tool,
    make_windows_app_list_tool,
    make_windows_window_focus_tool,
)
from app.models.capability import ExecutionLocation
from app.models.tool import PermissionLevel


def test_windows_app_list_tool_definition():
    tool = make_windows_app_list_tool()

    assert tool.name == "windows.app.list"
    assert tool.permission == PermissionLevel.L0
    assert tool.requires_confirmation is False
    assert tool.execution_location == ExecutionLocation.REMOTE
    assert tool.handler is None
    assert tool.timeout_seconds == 15.0
    assert tool.input_schema["required"] == ["device_id"]
    assert tool.input_schema["additionalProperties"] is False


def test_windows_app_launch_tool_definition():
    tool = make_windows_app_launch_tool()

    assert tool.name == "windows.app.launch"
    assert tool.permission == PermissionLevel.L1
    assert tool.requires_confirmation is False
    assert tool.execution_location == ExecutionLocation.REMOTE
    assert tool.handler is None
    assert tool.input_schema["required"] == ["device_id", "application"]
    assert tool.input_schema["additionalProperties"] is False


def test_windows_app_close_tool_definition():
    tool = make_windows_app_close_tool()

    assert tool.name == "windows.app.close"
    assert tool.permission == PermissionLevel.L2
    assert tool.requires_confirmation is False
    assert tool.execution_location == ExecutionLocation.REMOTE
    assert tool.handler is None
    assert tool.input_schema["required"] == ["device_id", "window_id"]
    assert tool.input_schema["additionalProperties"] is False


def test_windows_window_focus_tool_definition():
    tool = make_windows_window_focus_tool()

    assert tool.name == "windows.window.focus"
    assert tool.permission == PermissionLevel.L1
    assert tool.requires_confirmation is False
    assert tool.execution_location == ExecutionLocation.REMOTE
    assert tool.handler is None
    assert tool.input_schema["required"] == ["device_id", "window_id"]
    assert tool.input_schema["additionalProperties"] is False
