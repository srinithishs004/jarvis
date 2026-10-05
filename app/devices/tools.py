from app.models.capability import ExecutionLocation
from app.models.tool import PermissionLevel, ToolDefinition


def make_windows_system_info_tool() -> ToolDefinition:
    return ToolDefinition(
        name="windows.system.info",
        description="Read basic system information from a connected Windows JARVIS agent",
        permission=PermissionLevel.L0,
        timeout_seconds=15.0,
        input_schema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                },
            },
            "required": ["device_id"],
            "additionalProperties": False,
        },
        handler=None,
        execution_location=ExecutionLocation.REMOTE,
    )
