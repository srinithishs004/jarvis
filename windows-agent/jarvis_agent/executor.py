from __future__ import annotations

import platform
import socket
from typing import Any, Callable


class CommandExecutor:
    """Execute the small, explicitly allowlisted set of agent tools."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "windows.system.info": self._system_info,
        }

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        handler = self._handlers.get(tool_name)

        if handler is None:
            raise ValueError(f"Unsupported agent tool: {tool_name}")

        return handler(arguments)

    @staticmethod
    def _system_info(arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError(
                "windows.system.info does not accept arguments"
            )

        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }
