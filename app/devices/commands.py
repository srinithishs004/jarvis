import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from app.devices.connection import DeviceConnectionManager
from app.models.device_protocol import DeviceCommand, DeviceCommandResult


@dataclass
class _PendingCommand:
    event: threading.Event
    result: DeviceCommandResult | None = None


class DeviceCommandService:
    """Synchronous command/response transport over connected device WebSockets."""

    def __init__(
        self,
        connection_manager: DeviceConnectionManager,
    ) -> None:
        self.connection_manager = connection_manager
        self._pending: dict[str, _PendingCommand] = {}
        self._lock = threading.Lock()

    def execute(
        self,
        device_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout_seconds: float = 30.0,
        cancel_check: Callable[[], bool] | None = None,
        heartbeat: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        request_id = str(uuid4())
        pending = _PendingCommand(event=threading.Event())

        with self._lock:
            self._pending[request_id] = pending

        command = DeviceCommand(
            request_id=request_id,
            tool_name=tool_name,
            arguments=arguments or {},
        )

        try:
            sent = asyncio.run(
                self.connection_manager.send(
                    device_id,
                    command.model_dump(mode="json"),
                )
            )

            if not sent:
                return {
                    "ok": False,
                    "error": f"Device not connected: {device_id}",
                    "error_type": "device_not_connected",
                }

            deadline = time.monotonic() + timeout_seconds

            while True:
                if pending.event.wait(0.1):
                    break

                if cancel_check and cancel_check():
                    return {
                        "ok": False,
                        "error": "Device command cancelled",
                        "error_type": "cancelled",
                    }

                if heartbeat:
                    heartbeat()

                if time.monotonic() >= deadline:
                    return {
                        "ok": False,
                        "error": f"Device command timed out after {timeout_seconds} seconds",
                        "error_type": "timeout",
                    }

            result = pending.result

            if result is None:
                return {
                    "ok": False,
                    "error": "Device command completed without a result",
                    "error_type": "execution_error",
                }

            if result.success:
                return {
                    "ok": True,
                    "result": result.result,
                }

            return {
                "ok": False,
                "error": result.error or "Device command failed",
            }

        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def handle_result(self, result: DeviceCommandResult) -> bool:
        with self._lock:
            pending = self._pending.get(result.request_id)

            if pending is None:
                return False

            pending.result = result
            pending.event.set()
            return True

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)
