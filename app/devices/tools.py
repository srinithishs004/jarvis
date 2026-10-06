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


def make_windows_keyboard_type_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.keyboard.type",
        description="Type text into the currently focused window on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "text": {"type": "string"},
        },
        required=["device_id", "text"],
    )


def make_windows_keyboard_press_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.keyboard.press",
        description="Press an explicitly allowlisted keyboard key on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "key": {"type": "string"},
        },
        required=["device_id", "key"],
    )


def make_windows_mouse_move_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.mouse.move",
        description="Move the mouse cursor to screen coordinates on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "x": {"type": "integer", "minimum": 0},
            "y": {"type": "integer", "minimum": 0},
        },
        required=["device_id", "x", "y"],
    )


def make_windows_mouse_click_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.mouse.click",
        description="Click an explicitly supported mouse button at screen coordinates on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "x": {"type": "integer", "minimum": 0},
            "y": {"type": "integer", "minimum": 0},
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
            },
        },
        required=["device_id", "x", "y", "button"],
    )

def make_windows_clipboard_read_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.clipboard.read",
        description="Read text from the clipboard on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
        },
        required=["device_id"],
    )


def make_windows_clipboard_write_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.clipboard.write",
        description="Write text to the clipboard on a connected Windows JARVIS agent",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "text": {"type": "string"},
        },
        required=["device_id", "text"],
    )


def make_windows_filesystem_read_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.filesystem.read",
        description="Read a text file beneath the configured Windows JARVIS filesystem root",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "path": {"type": "string"},
        },
        required=["device_id", "path"],
    )


def make_windows_filesystem_list_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.filesystem.list",
        description="List entries in a directory beneath the configured Windows JARVIS filesystem root",
        permission=PermissionLevel.L1,
        timeout_seconds=15.0,
        properties={
            "device_id": {"type": "string"},
            "path": {"type": "string"},
        },
        required=["device_id", "path"],
    )


def make_windows_filesystem_write_tool() -> ToolDefinition:
    return _windows_tool(
        name="windows.filesystem.write",
        description="Write text to a file beneath the configured Windows JARVIS filesystem root",
        permission=PermissionLevel.L2,
        timeout_seconds=20.0,
        properties={
            "device_id": {"type": "string"},
            "path": {"type": "string"},
            "text": {"type": "string"},
        },
        required=["device_id", "path", "text"],
    )
