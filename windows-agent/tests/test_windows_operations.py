import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from jarvis_agent.windows_operations import NativeWindowsOperations


def test_native_operations_requires_windows():
    if sys.platform == "win32":
        pytest.skip("Only verifies the non-Windows guard")

    with pytest.raises(RuntimeError, match="requires Windows"):
        NativeWindowsOperations(".")


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

@pytest.mark.parametrize("value", [None, 123, b"text", True])
def test_clipboard_write_rejects_non_string_values(value):
    operation = object.__new__(NativeWindowsOperations)

    with pytest.raises(ValueError, match="text must be a string"):
        operation.write_clipboard(value)


def test_clipboard_write_rejects_empty_text():
    operation = object.__new__(NativeWindowsOperations)

    with pytest.raises(ValueError, match="text must not be empty"):
        operation.write_clipboard("")


def make_filesystem_operation(tmp_path):
    operation = object.__new__(NativeWindowsOperations)
    operation._filesystem_root = tmp_path.resolve()
    return operation


def test_filesystem_read_returns_utf8_text(tmp_path):
    operation = make_filesystem_operation(tmp_path)
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    result = operation.read_file("notes.txt")

    assert result == {
        "path": "notes.txt",
        "text": "hello",
        "bytes": 5,
    }


def test_filesystem_read_rejects_absolute_path(tmp_path):
    operation = make_filesystem_operation(tmp_path)

    with pytest.raises(ValueError, match="Absolute filesystem paths are not allowed"):
        operation.read_file(str(tmp_path / "notes.txt"))


def test_filesystem_read_rejects_parent_traversal(tmp_path):
    operation = make_filesystem_operation(tmp_path)

    with pytest.raises(ValueError, match="Parent traversal is not allowed"):
        operation.read_file("../notes.txt")


def test_filesystem_read_rejects_symlink(tmp_path):
    operation = make_filesystem_operation(tmp_path)
    target = tmp_path / "target.txt"
    target.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    with pytest.raises(ValueError, match="Symlinks and junctions are not allowed"):
        operation.read_file("link.txt")


def test_filesystem_read_rejects_oversized_file(tmp_path):
    operation = make_filesystem_operation(tmp_path)
    (tmp_path / "large.txt").write_bytes(
        b"x" * (NativeWindowsOperations.MAX_FILE_SIZE_BYTES + 1)
    )

    with pytest.raises(ValueError, match="maximum allowed size"):
        operation.read_file("large.txt")


def test_filesystem_list_directory_returns_entries(tmp_path):
    operation = make_filesystem_operation(tmp_path)
    (tmp_path / "b.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "docs").mkdir()

    result = operation.list_directory(".")

    assert result["path"] == "."
    assert result["entries"] == [
        {"name": "b.txt", "type": "file", "bytes": 5},
        {"name": "docs", "type": "directory"},
    ]


def test_filesystem_list_rejects_symlink_entry(tmp_path):
    operation = make_filesystem_operation(tmp_path)
    target = tmp_path / "target.txt"
    target.write_text("secret", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(target)

    with pytest.raises(ValueError, match="unsupported symlink"):
        operation.list_directory(".")


def test_filesystem_write_creates_file(tmp_path):
    operation = make_filesystem_operation(tmp_path)

    result = operation.write_file("notes.txt", "hello")

    assert result == {
        "path": "notes.txt",
        "bytes": 5,
        "written": True,
    }
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "hello"


def test_filesystem_write_rejects_absolute_path(tmp_path):
    operation = make_filesystem_operation(tmp_path)

    with pytest.raises(ValueError, match="Absolute filesystem paths are not allowed"):
        operation.write_file(str(tmp_path / "notes.txt"), "hello")


def test_filesystem_write_rejects_parent_traversal(tmp_path):
    operation = make_filesystem_operation(tmp_path)

    with pytest.raises(ValueError, match="Parent traversal is not allowed"):
        operation.write_file("../notes.txt", "hello")


def test_filesystem_write_rejects_oversized_text(tmp_path):
    operation = make_filesystem_operation(tmp_path)

    with pytest.raises(ValueError, match="maximum allowed file size"):
        operation.write_file(
            "large.txt",
            "x" * (NativeWindowsOperations.MAX_FILE_SIZE_BYTES + 1),
        )


def test_filesystem_write_rejects_directory_target(tmp_path):
    operation = make_filesystem_operation(tmp_path)
    (tmp_path / "docs").mkdir()

    with pytest.raises(ValueError, match="regular file"):
        operation.write_file("docs", "hello")
