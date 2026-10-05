from typing import Any, Callable

from app.devices.commands import DeviceCommandService


class RemoteToolExecutor:
    """Execute ToolRouter remote tools through the device command transport."""

    def __init__(
        self,
        command_service: DeviceCommandService,
    ) -> None:
        self.command_service = command_service

    def run(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float,
        cancel_check: Callable[[], bool] | None = None,
        heartbeat: Callable[[], bool] | None = None,
    ) -> tuple[str, Any]:
        device_id = arguments["device_id"]
        device_arguments = {
            key: value
            for key, value in arguments.items()
            if key != "device_id"
        }

        result = self.command_service.execute(
            device_id=device_id,
            tool_name=tool_name,
            arguments=device_arguments,
            timeout_seconds=timeout_seconds,
            cancel_check=cancel_check,
            heartbeat=heartbeat,
        )

        if result.get("ok"):
            return "succeeded", result.get("result")

        error_type = result.get("error_type")

        if error_type == "cancelled":
            return "cancelled", None

        if error_type == "timeout":
            return "timeout", None

        return (
            error_type or "execution_error",
            result.get("error", "Remote tool execution failed"),
        )
