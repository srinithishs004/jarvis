from __future__ import annotations

import os
from typing import Any


class NativeWindowsOperations:
    """Native Windows GUI operations with an explicit application allowlist."""

    ALLOWED_KEYS = frozenset(
        {
            "BACKSPACE",
            "TAB",
            "ENTER",
            "ESC",
            "SPACE",
            "LEFT",
            "UP",
            "RIGHT",
            "DOWN",
            "HOME",
            "END",
            "PAGEUP",
            "PAGEDOWN",
            "INSERT",
            "DELETE",
            "SHIFT",
            "CTRL",
            "ALT",
            "WIN",
            "F1",
            "F2",
            "F3",
            "F4",
            "F5",
            "F6",
            "F7",
            "F8",
            "F9",
            "F10",
            "F11",
            "F12",
        }
    )

    KEY_VIRTUAL_CODES = {
        "BACKSPACE": 0x08,
        "TAB": 0x09,
        "ENTER": 0x0D,
        "ESC": 0x1B,
        "SPACE": 0x20,
        "LEFT": 0x25,
        "UP": 0x26,
        "RIGHT": 0x27,
        "DOWN": 0x28,
        "HOME": 0x24,
        "END": 0x23,
        "PAGEUP": 0x21,
        "PAGEDOWN": 0x22,
        "INSERT": 0x2D,
        "DELETE": 0x2E,
        "SHIFT": 0x10,
        "CTRL": 0x11,
        "ALT": 0x12,
        "WIN": 0x5B,
        "F1": 0x70,
        "F2": 0x71,
        "F3": 0x72,
        "F4": 0x73,
        "F5": 0x74,
        "F6": 0x75,
        "F7": 0x76,
        "F8": 0x77,
        "F9": 0x78,
        "F10": 0x79,
        "F11": 0x7A,
        "F12": 0x7B,
    }

    ALLOWED_MOUSE_BUTTONS = frozenset(
        {"left", "right", "middle"}
    )

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

    def type_text(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise ValueError("text must be a string")

        if not text:
            raise ValueError("text must not be empty")

        import ctypes

        user32 = ctypes.windll.user32
        input_type = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("ki", KEYBDINPUT),
            ]

        inputs = []
        for character in text:
            codepoint = ord(character)
            if codepoint > 0xFFFF:
                raise ValueError(
                    "text contains unsupported Unicode code point"
                )

            inputs.append(
                INPUT(
                    type=input_type,
                    ki=KEYBDINPUT(
                        wVk=0,
                        wScan=codepoint,
                        dwFlags=KEYEVENTF_UNICODE,
                        time=0,
                        dwExtraInfo=None,
                    ),
                )
            )
            inputs.append(
                INPUT(
                    type=input_type,
                    ki=KEYBDINPUT(
                        wVk=0,
                        wScan=codepoint,
                        dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                        time=0,
                        dwExtraInfo=None,
                    ),
                )
            )

        array_type = INPUT * len(inputs)
        sent = user32.SendInput(
            len(inputs),
            array_type(*inputs),
            ctypes.sizeof(INPUT),
        )

        if sent != len(inputs):
            raise OSError("SendInput failed while typing text")

        return {"typed": text, "characters": len(text)}

    def press_key(self, key: str) -> dict[str, Any]:
        normalized = key.strip().upper()

        if normalized not in self.ALLOWED_KEYS:
            raise ValueError(f"Key is not allowlisted: {key}")

        virtual_key = self.KEY_VIRTUAL_CODES[normalized]

        import ctypes

        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("ki", KEYBDINPUT),
            ]

        input_type = 1
        inputs = (
            INPUT(
                type=input_type,
                ki=KEYBDINPUT(
                    wVk=virtual_key,
                    wScan=0,
                    dwFlags=0,
                    time=0,
                    dwExtraInfo=None,
                ),
            ),
            INPUT(
                type=input_type,
                ki=KEYBDINPUT(
                    wVk=virtual_key,
                    wScan=0,
                    dwFlags=KEYEVENTF_KEYUP,
                    time=0,
                    dwExtraInfo=None,
                ),
            ),
        )

        array_type = INPUT * 2
        sent = user32.SendInput(
            2,
            array_type(*inputs),
            ctypes.sizeof(INPUT),
        )

        if sent != 2:
            raise OSError("SendInput failed while pressing key")

        return {"key": normalized, "pressed": True}

    def move_mouse(self, x: int, y: int) -> dict[str, Any]:
        if isinstance(x, bool) or not isinstance(x, int) or x < 0:
            raise ValueError("x must be a non-negative integer")
        if isinstance(y, bool) or not isinstance(y, int) or y < 0:
            raise ValueError("y must be a non-negative integer")

        import ctypes

        user32 = ctypes.windll.user32
        if not user32.SetCursorPos(x, y):
            raise OSError("SetCursorPos failed")

        return {"x": x, "y": y, "moved": True}

    def click_mouse(
        self,
        x: int,
        y: int,
        button: str,
    ) -> dict[str, Any]:
        self.move_mouse(x, y)

        normalized = button.strip().lower()
        if normalized not in self.ALLOWED_MOUSE_BUTTONS:
            raise ValueError(
                f"Mouse button is not allowlisted: {button}"
            )

        flags = {
            "left": (0x0002, 0x0004),
            "right": (0x0008, 0x0010),
            "middle": (0x0020, 0x0040),
        }[normalized]

        import ctypes

        user32 = ctypes.windll.user32

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("mi", MOUSEINPUT),
            ]

        inputs = (
            INPUT(
                type=0,
                mi=MOUSEINPUT(
                    dx=0,
                    dy=0,
                    mouseData=0,
                    dwFlags=flags[0],
                    time=0,
                    dwExtraInfo=None,
                ),
            ),
            INPUT(
                type=0,
                mi=MOUSEINPUT(
                    dx=0,
                    dy=0,
                    mouseData=0,
                    dwFlags=flags[1],
                    time=0,
                    dwExtraInfo=None,
                ),
            ),
        )

        array_type = INPUT * 2
        sent = user32.SendInput(
            2,
            array_type(*inputs),
            ctypes.sizeof(INPUT),
        )

        if sent != 2:
            raise OSError("SendInput failed while clicking mouse")

        return {
            "x": x,
            "y": y,
            "button": normalized,
            "clicked": True,
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
