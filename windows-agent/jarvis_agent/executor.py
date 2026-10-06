from __future__ import annotations

import platform
import socket
from typing import Any, Callable, Protocol


class WindowsOperations(Protocol):
    def list_applications(self) -> Any:
        ...

    def launch_application(self, application: str) -> Any:
        ...

    def close_window(self, window_id: str) -> Any:
        ...

    def focus_window(self, window_id: str) -> Any:
        ...


class CommandExecutor:
    """Execute the small, explicitly allowlisted set of agent tools."""

    def __init__(
        self,
        operations: WindowsOperations | None = None,
    ) -> None:
        self._operations = operations or _DefaultWindowsOperations()

        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "windows.system.info": self._system_info,
            "windows.app.list": self._app_list,
            "windows.app.launch": self._app_launch,
            "windows.app.close": self._app_close,
            "windows.window.focus": self._window_focus,
        }

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        handler = self._handlers.get(tool_name)

        if handler is None:
            raise ValueError(f"Unsupported agent tool: {tool_name}")

        if not isinstance(arguments, dict):
            raise ValueError("Invalid arguments: expected an object")

        return handler(arguments)

    @staticmethod
    def _system_info(arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError(
                "Invalid arguments: windows.system.info does not accept arguments"
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

    def _app_list(self, arguments: dict[str, Any]) -> Any:
        if arguments:
            raise ValueError(
                "Invalid arguments: windows.app.list does not accept arguments"
            )

        return self._operations.list_applications()

    def _app_launch(self, arguments: dict[str, Any]) -> Any:
        self._require_string_argument(
            arguments,
            tool_name="windows.app.launch",
            argument_name="application",
        )

        if set(arguments) != {"application"}:
            raise ValueError(
                "Invalid arguments: windows.app.launch expects only "
                "'application'"
            )

        return self._operations.launch_application(arguments["application"])

    def _app_close(self, arguments: dict[str, Any]) -> Any:
        self._require_string_argument(
            arguments,
            tool_name="windows.app.close",
            argument_name="window_id",
        )

        if set(arguments) != {"window_id"}:
            raise ValueError(
                "Invalid arguments: windows.app.close expects only "
                "'window_id'"
            )

        return self._operations.close_window(arguments["window_id"])

    def _window_focus(self, arguments: dict[str, Any]) -> Any:
        self._require_string_argument(
            arguments,
            tool_name="windows.window.focus",
            argument_name="window_id",
        )

        if set(arguments) != {"window_id"}:
            raise ValueError(
                "Invalid arguments: windows.window.focus expects only "
                "'window_id'"
            )

        return self._operations.focus_window(arguments["window_id"])

    @staticmethod
    def _require_string_argument(
        arguments: dict[str, Any],
        *,
        tool_name: str,
        argument_name: str,
    ) -> None:
        if argument_name not in arguments:
            raise ValueError(
                f"Invalid arguments: {tool_name} requires '{argument_name}'"
            )

        if not isinstance(arguments[argument_name], str):
            raise ValueError(
                f"Invalid arguments: {tool_name} '{argument_name}' "
                "must be a string"
            )

        if not arguments[argument_name].strip():
            raise ValueError(
                f"Invalid arguments: {tool_name} '{argument_name}' "
                "must not be empty"
            )


class _DefaultWindowsOperations:
    """Placeholder backend until the native Windows implementation exists."""

    def list_applications(self) -> Any:
        raise RuntimeError("Windows application operations are unavailable")

    def launch_application(self, application: str) -> Any:
        raise RuntimeError("Windows application operations are unavailable")

    def close_window(self, window_id: str) -> Any:
        raise RuntimeError("Windows window operations are unavailable")

    def focus_window(self, window_id: str) -> Any:
        raise RuntimeError("Windows window operations are unavailable")
