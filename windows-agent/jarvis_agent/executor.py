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

    def type_text(self, text: str) -> Any:
        ...

    def press_key(self, key: str) -> Any:
        ...

    def move_mouse(self, x: int, y: int) -> Any:
        ...

    def click_mouse(self, x: int, y: int, button: str) -> Any:
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
            "windows.keyboard.type": self._keyboard_type,
            "windows.keyboard.press": self._keyboard_press,
            "windows.mouse.move": self._mouse_move,
            "windows.mouse.click": self._mouse_click,
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

    def _keyboard_type(self, arguments: dict[str, Any]) -> Any:
        self._require_string_argument(
            arguments,
            tool_name="windows.keyboard.type",
            argument_name="text",
        )
        if set(arguments) != {"text"}:
            raise ValueError(
                "Invalid arguments: windows.keyboard.type expects only 'text'"
            )
        return self._operations.type_text(arguments["text"])

    def _keyboard_press(self, arguments: dict[str, Any]) -> Any:
        self._require_string_argument(
            arguments,
            tool_name="windows.keyboard.press",
            argument_name="key",
        )
        if set(arguments) != {"key"}:
            raise ValueError(
                "Invalid arguments: windows.keyboard.press expects only 'key'"
            )
        return self._operations.press_key(arguments["key"])

    def _mouse_move(self, arguments: dict[str, Any]) -> Any:
        self._require_coordinate_arguments(
            arguments,
            tool_name="windows.mouse.move",
        )
        if set(arguments) != {"x", "y"}:
            raise ValueError(
                "Invalid arguments: windows.mouse.move expects only 'x' and 'y'"
            )
        return self._operations.move_mouse(
            arguments["x"],
            arguments["y"],
        )

    def _mouse_click(self, arguments: dict[str, Any]) -> Any:
        self._require_coordinate_arguments(
            arguments,
            tool_name="windows.mouse.click",
        )
        self._require_string_argument(
            arguments,
            tool_name="windows.mouse.click",
            argument_name="button",
        )
        if set(arguments) != {"x", "y", "button"}:
            raise ValueError(
                "Invalid arguments: windows.mouse.click expects only "
                "'x', 'y', and 'button'"
            )
        return self._operations.click_mouse(
            arguments["x"],
            arguments["y"],
            arguments["button"],
        )

    @staticmethod
    def _require_coordinate_arguments(
        arguments: dict[str, Any],
        *,
        tool_name: str,
    ) -> None:
        for argument_name in ("x", "y"):
            if argument_name not in arguments:
                raise ValueError(
                    f"Invalid arguments: {tool_name} requires '{argument_name}'"
                )
            value = arguments[argument_name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"Invalid arguments: {tool_name} '{argument_name}' "
                    "must be an integer"
                )
            if value < 0:
                raise ValueError(
                    f"Invalid arguments: {tool_name} '{argument_name}' "
                    "must be non-negative"
                )

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

    def type_text(self, text: str) -> Any:
        raise RuntimeError("Windows keyboard operations are unavailable")

    def press_key(self, key: str) -> Any:
        raise RuntimeError("Windows keyboard operations are unavailable")

    def move_mouse(self, x: int, y: int) -> Any:
        raise RuntimeError("Windows mouse operations are unavailable")

    def click_mouse(self, x: int, y: int, button: str) -> Any:
        raise RuntimeError("Windows mouse operations are unavailable")
