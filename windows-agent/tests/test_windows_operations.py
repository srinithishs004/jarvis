import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from jarvis_agent.windows_operations import NativeWindowsOperations


def test_native_operations_requires_windows():
    if sys.platform == "win32":
        pytest.skip("Only verifies the non-Windows guard")

    with pytest.raises(RuntimeError, match="requires Windows"):
        NativeWindowsOperations()


def test_allowed_application_set_is_explicit():
    assert NativeWindowsOperations.ALLOWED_APPLICATIONS == frozenset(
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


@pytest.mark.parametrize(
    "window_id",
    [
        "",
        "abc",
        "0",
        "-1",
        "1.5",
    ],
)
def test_window_id_rejects_invalid_values(window_id):
    with pytest.raises(ValueError, match="Invalid window_id"):
        NativeWindowsOperations._parse_window_id(window_id)


@pytest.mark.parametrize(
    ("window_id", "expected"),
    [
        ("1", 1),
        ("42", 42),
        ("65535", 65535),
    ],
)
def test_window_id_accepts_positive_decimal_values(window_id, expected):
    assert NativeWindowsOperations._parse_window_id(window_id) == expected
