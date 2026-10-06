from app.devices.capabilities import (
    WINDOWS_CAPABILITY_NAMES,
    WINDOWS_TOOL_NAMES,
    allowed_capability_names,
    allowed_tool_names,
)
from app.models.device import DeviceType


def test_windows_tool_allowlist_contains_registered_windows_tools():
    assert WINDOWS_TOOL_NAMES == {
        "windows.system.info",
        "windows.app.list",
        "windows.app.launch",
        "windows.app.close",
        "windows.window.focus",
        "windows.keyboard.type",
        "windows.keyboard.press",
        "windows.mouse.move",
        "windows.mouse.click",
        "windows.clipboard.read",
        "windows.clipboard.write",
    }


def test_windows_capability_allowlist_contains_expected_capabilities():
    assert WINDOWS_CAPABILITY_NAMES == {
        "system.info",
        "app.list",
        "app.launch",
        "app.close",
        "window.focus",
        "keyboard.type",
        "keyboard.press",
        "mouse.move",
        "mouse.click",
        "clipboard.read",
        "clipboard.write",
    }


def test_windows_allowlists_are_returned_for_windows_devices():
    assert allowed_tool_names(DeviceType.WINDOWS) == WINDOWS_TOOL_NAMES
    assert (
        allowed_capability_names(DeviceType.WINDOWS)
        == WINDOWS_CAPABILITY_NAMES
    )


def test_sanitize_windows_capabilities_filters_unknown_names():
    from app.devices.capabilities import sanitize_device_capabilities
    from app.models.device import DeviceCapabilities

    sanitized = sanitize_device_capabilities(
        DeviceType.WINDOWS,
        DeviceCapabilities(
            capabilities=[
                "app.list",
                "keyboard",
                "unknown.capability",
            ],
            tool_names=[
                "windows.app.list",
                "windows.keyboard",
                "windows.unknown",
            ],
        ),
    )

    assert sanitized.capabilities == ["app.list"]
    assert sanitized.tool_names == ["windows.app.list"]
