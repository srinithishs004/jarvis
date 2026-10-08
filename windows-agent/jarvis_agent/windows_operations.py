from __future__ import annotations

import base64
import ctypes
import os
from pathlib import Path
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

    MAX_FILE_SIZE_BYTES = 1024 * 1024
    MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024

    def __init__(self, filesystem_root: str) -> None:
        if os.name != "nt":
            raise RuntimeError(
                "NativeWindowsOperations requires Windows"
            )

        if not isinstance(filesystem_root, str) or not filesystem_root.strip():
            raise ValueError("filesystem_root must be a non-empty string")

        root = Path(filesystem_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("filesystem_root must be an existing directory")

        self._filesystem_root = root

    def read_file(self, path: str) -> dict[str, Any]:
        target = self._resolve_filesystem_path(path, must_exist=True)

        if not target.is_file() or target.is_symlink():
            raise ValueError("Filesystem path is not a regular file")

        size = target.stat().st_size
        if size > self.MAX_FILE_SIZE_BYTES:
            raise ValueError("File exceeds the maximum allowed size")

        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("File is not valid UTF-8 text") from exc

        return {
            "path": self._relative_filesystem_path(target),
            "text": text,
            "bytes": len(text.encode("utf-8")),
        }

    def list_directory(self, path: str) -> dict[str, Any]:
        target = self._resolve_filesystem_path(path, must_exist=True)

        if not target.is_dir() or target.is_symlink():
            raise ValueError("Filesystem path is not a directory")

        entries: list[dict[str, Any]] = []
        for entry in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            if entry.is_symlink():
                raise ValueError(
                    f"Directory contains unsupported symlink: {entry.name}"
                )

            item: dict[str, Any] = {
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
            }

            if entry.is_file():
                item["bytes"] = entry.stat().st_size

            entries.append(item)

        return {
            "path": self._relative_filesystem_path(target),
            "entries": entries,
        }

    def write_file(self, path: str, text: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise ValueError("text must be a string")

        if len(text.encode("utf-8")) > self.MAX_FILE_SIZE_BYTES:
            raise ValueError("Text exceeds the maximum allowed file size")

        target = self._resolve_filesystem_path(path, must_exist=False)

        if target.exists():
            if not target.is_file() or target.is_symlink():
                raise ValueError("Filesystem path is not a regular file")

        parent = target.parent
        if not parent.is_dir() or parent.is_symlink():
            raise ValueError("Parent directory is invalid")

        target.write_text(text, encoding="utf-8")

        return {
            "path": self._relative_filesystem_path(target),
            "bytes": len(text.encode("utf-8")),
            "written": True,
        }

    def _resolve_filesystem_path(
        self,
        path: str,
        *,
        must_exist: bool,
    ) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Filesystem path must be a non-empty string")

        if "\x00" in path:
            raise ValueError("Filesystem path contains a null byte")

        candidate_path = Path(path)

        if candidate_path.is_absolute() or candidate_path.drive:
            raise ValueError("Absolute filesystem paths are not allowed")

        if ".." in candidate_path.parts:
            raise ValueError("Parent traversal is not allowed")

        candidate = self._filesystem_root / candidate_path

        current = self._filesystem_root
        for part in candidate_path.parts:
            current = current / part
            if current.is_symlink() or current.is_junction():
                raise ValueError("Symlinks and junctions are not allowed")

        if must_exist:
            resolved = candidate.resolve(strict=True)
        else:
            resolved = candidate.resolve(strict=False)

        try:
            resolved.relative_to(self._filesystem_root)
        except ValueError as exc:
            raise ValueError("Filesystem path escapes configured root") from exc

        return resolved

    def _relative_filesystem_path(self, path: Path) -> str:
        return path.relative_to(self._filesystem_root).as_posix()

    def capture_screen(self) -> dict[str, Any]:
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)

        if width <= 0 or height <= 0:
            raise OSError("Invalid screen dimensions")

        hdc_screen = user32.GetDC(None)
        if not hdc_screen:
            raise OSError("GetDC failed")

        hdc_memory = None
        bitmap = None
        old_bitmap = None

        try:
            hdc_memory = gdi32.CreateCompatibleDC(hdc_screen)
            if not hdc_memory:
                raise OSError("CreateCompatibleDC failed")

            bitmap = gdi32.CreateCompatibleBitmap(
                hdc_screen,
                width,
                height,
            )
            if not bitmap:
                raise OSError("CreateCompatibleBitmap failed")

            old_bitmap = gdi32.SelectObject(hdc_memory, bitmap)
            if not old_bitmap:
                raise OSError("SelectObject failed")

            SRCCOPY = 0x00CC0020
            if not gdi32.BitBlt(
                hdc_memory,
                0,
                0,
                width,
                height,
                hdc_screen,
                0,
                0,
                SRCCOPY,
            ):
                raise OSError("BitBlt failed")

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            header = BITMAPINFOHEADER()
            header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            header.biWidth = width
            header.biHeight = -height
            header.biPlanes = 1
            header.biBitCount = 32
            header.biCompression = 0

            buffer_size = width * 4 * height
            if buffer_size > self.MAX_SCREENSHOT_BYTES:
                raise ValueError(
                    "Screen capture exceeds the maximum supported size"
                )

            pixels = ctypes.create_string_buffer(buffer_size)

            gdi32.GetDIBits.argtypes = [
                wintypes.HDC,
                wintypes.HBITMAP,
                wintypes.UINT,
                wintypes.UINT,
                ctypes.c_void_p,
                ctypes.POINTER(BITMAPINFOHEADER),
                wintypes.UINT,
            ]
            gdi32.GetDIBits.restype = wintypes.INT

            copied = gdi32.GetDIBits(
                hdc_memory,
                bitmap,
                0,
                height,
                pixels,
                ctypes.byref(header),
                0,
            )
            if copied != height:
                raise OSError("GetDIBits failed")

            encoded = base64.b64encode(pixels.raw).decode("ascii")

            return {
                "width": width,
                "height": height,
                "format": "BGRA",
                "data": encoded,
            }
        finally:
            if old_bitmap and hdc_memory:
                gdi32.SelectObject(hdc_memory, old_bitmap)
            if bitmap:
                gdi32.DeleteObject(bitmap)
            if hdc_memory:
                gdi32.DeleteDC(hdc_memory)
            user32.ReleaseDC(None, hdc_screen)

    def list_applications(self) -> list[dict[str, Any]]:
        import ctypes
        import ctypes.wintypes as wintypes

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


    def read_clipboard(self) -> dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13

        if not user32.OpenClipboard(None):
            raise OSError("OpenClipboard failed")

        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                raise ValueError("Clipboard does not contain text")

            kernel32.GlobalLock.restype = ctypes.c_void_p
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                raise OSError("GlobalLock failed")

            try:
                text = ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)

            return {
                "text": text,
            }
        finally:
            user32.CloseClipboard()

    def write_clipboard(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise ValueError("text must be a string")

        if not text:
            raise ValueError("text must not be empty")

        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        GMEM_ZEROINIT = 0x0040

        encoded = ctypes.create_unicode_buffer(text)
        size = ctypes.sizeof(encoded)

        if not user32.OpenClipboard(None):
            raise OSError("OpenClipboard failed")

        handle = None

        try:
            if not user32.EmptyClipboard():
                raise OSError("EmptyClipboard failed")

            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, size)
            if not handle:
                raise MemoryError("GlobalAlloc failed")

            kernel32.GlobalLock.restype = ctypes.c_void_p
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                handle = None
                raise OSError("GlobalLock failed")

            try:
                ctypes.memmove(pointer, encoded, size)
            finally:
                kernel32.GlobalUnlock(handle)

            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                kernel32.GlobalFree(handle)
                handle = None
                raise OSError("SetClipboardData failed")

            # Ownership transfers to the clipboard after SetClipboardData.
            handle = None

            return {
                "written": text,
                "characters": len(text),
            }
        finally:
            user32.CloseClipboard()
            if handle:
                kernel32.GlobalFree(handle)
