from app.devices.tools import (
    make_windows_screen_capture_tool,
    make_windows_system_info_tool,
)
from app.models.capability import ExecutionLocation
from app.models.tool import PermissionLevel


def test_windows_system_info_tool_definition():
    tool = make_windows_system_info_tool()

    assert tool.name == "windows.system.info"
    assert tool.permission == PermissionLevel.L0
    assert tool.requires_confirmation is False
    assert tool.execution_location == ExecutionLocation.REMOTE
    assert tool.handler is None
    assert tool.timeout_seconds == 15.0
    assert tool.input_schema["required"] == ["device_id"]
    assert tool.input_schema["additionalProperties"] is False


def test_windows_system_info_tool_has_no_local_execution_handler():
    tool = make_windows_system_info_tool()

    assert tool.handler is None


def test_windows_screen_capture_tool_definition():
    tool = make_windows_screen_capture_tool()

    assert tool.name == "windows.screen.capture"
    assert tool.permission == PermissionLevel.L1
    assert tool.requires_confirmation is False
    assert tool.execution_location == ExecutionLocation.REMOTE
    assert tool.handler is None
    assert tool.timeout_seconds == 15.0
    assert tool.input_schema["required"] == ["device_id"]
    assert tool.input_schema["additionalProperties"] is False
