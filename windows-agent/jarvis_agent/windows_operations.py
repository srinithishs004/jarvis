from __future__ import annotations

import os
from typing import Any


class NativeWindowsOperations:
    """Native Windows GUI operations with an explicit application allowlist."""

    ALLOWED_APPLICATIONS = frozenset(
        {
            "notepad",
            "notepad.exe",
            "calc",
            "calc.exe",
            "mspaint",
            "mspaint.exe",
            "explorer",
            "explorer.exe",
        }
    )

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError(
                "NativeWindowsOperations requires Windows"
            )

    def list_applications(self) -> list[dict[str, Any]]:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        windows: list[dict[str, Any]] = []

        enum_windows_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)

            title = buffer.value.strip()
            if not title:
                return True

            windows.append(
                {
                    "window_id": str(hwnd),
                    "title": title,
                }
            )
            return True

        callback_ref = enum_windows_proc(callback)

        if not user32.EnumWindows(callback_ref, 0):
            raise OSError("EnumWindows failed")

        return windows

    def launch_application(self, application: str) -> dict[str, Any]:
        import subprocess

        normalized = application.strip().lower()

        if normalized not in self.ALLOWED_APPLICATIONS:
            raise ValueError(
                f"Application is not allowlisted: {application}"
            )

        # Do not invoke a shell. The application is passed directly to
        # CreateProcess via subprocess with shell=False.
        process = subprocess.Popen(
            [normalized],
            shell=False,
            close_fds=True,
        )

        return {
            "application": normalized,
            "pid": process.pid,
            "launched": True,
        }

    def close_window(self, window_id: str) -> dict[str, Any]:
        hwnd = self._parse_window_id(window_id)

        import ctypes

        user32 = ctypes.windll.user32

        if not user32.IsWindow(hwnd):
            raise ValueError(f"Window does not exist: {window_id}")

        if not user32.PostMessageW(hwnd, 0x0010, 0, 0):
            raise OSError("Failed to request window close")

        return {
            "window_id": window_id,
            "closed": True,
        }

    def focus_window(self, window_id: str) -> dict[str, Any]:
        hwnd = self._parse_window_id(window_id)

        import ctypes

        user32 = ctypes.windll.user32

        if not user32.IsWindow(hwnd):
            raise ValueError(f"Window does not exist: {window_id}")

        if not user32.SetForegroundWindow(hwnd):
            raise OSError("Failed to focus window")

        return {
            "window_id": window_id,
            "focused": True,
        }

    @staticmethod
    def _parse_window_id(window_id: str) -> int:
        try:
            hwnd = int(window_id, 10)
        except ValueError as exc:
            raise ValueError(
                f"Invalid window_id: {window_id}"
            ) from exc

        if hwnd <= 0:
            raise ValueError(
                f"Invalid window_id: {window_id}"
            )

        return hwnd
