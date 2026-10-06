from app.models.capability import ExecutionLocation
from app.models.tool import PermissionLevel, ToolDefinition


def _windows_tool(
    *,
    name: str,
    description: str,
    permission: PermissionLevel,
    timeout_seconds: float,
    properties: dict,
    required: list[str],
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        permission=permission,
        timeout_seconds=timeout_seconds,
        input_schema={
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        handler=None,
        execution_location=ExecutionLocation.REMOTE,
    )


def make_windows_system_info_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.system.info",
        description="Read basic system information from a connected Windows JARVIS agent",
        permission=PermissionLevel.L0,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
        },
        required=["device_id"],
    )


def make_windows_app_list_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.app.list",
        description="List running applications and their windows on a connected Windows JARVIS agent",
        permission=PermissionLevel.L0,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
        },
        required=["device_id"],
    )


def make_windows_app_launch_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.app.launch",
        description="Launch an allowlisted application on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=20.0,
        properties={
            "device_id": {"type": "string"},
            "application": {"type": "string"},
        },
        required=["device_id", "application"],
    )


def make_windows_app_close_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.app.close",
        description="Close an application or window on a connected Windows JARVIS agent",
        permission=PermissionLevel.L2,
        timeout_seconds=20.0,
        properties={
            "device_id": {"type": "string"},
            "window_id": {"type": "string"},
        },
        required=["device_id", "window_id"],
    )


def make_windows_window_focus_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.window.focus",
        description="Focus an existing application window on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "window_id": {"type": "string"},
        },
        required=["device_id", "window_id"],
    )
