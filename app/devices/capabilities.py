from app.models.device import DeviceCapabilities, DeviceType


WINDOWS_TOOL_NAMES = frozenset(
    {
        "windows.system.info",
        "windows.app.list",
        "windows.app.launch",
        "windows.app.close",
        "windows.window.focus",
    }
)

WINDOWS_CAPABILITY_NAMES = frozenset(
    {
        "system.info",
        "app.list",
        "app.launch",
        "app.close",
        "window.focus",
    }
)


def allowed_tool_names(device_type: DeviceType) -> frozenset[str]:
    if device_type == DeviceType.WINDOWS:
        return WINDOWS_TOOL_NAMES

    return frozenset()


def allowed_capability_names(device_type: DeviceType) -> frozenset[str]:
    if device_type == DeviceType.WINDOWS:
        return WINDOWS_CAPABILITY_NAMES

    return frozenset()


def sanitize_device_capabilities(
    device_type: DeviceType,
    capabilities: DeviceCapabilities,
) -> DeviceCapabilities:
    allowed_tools = allowed_tool_names(device_type)
    allowed_capabilities = allowed_capability_names(device_type)

    return DeviceCapabilities(
        capabilities=[
            capability
            for capability in capabilities.capabilities
            if capability in allowed_capabilities
        ],
        tool_names=[
            tool_name
            for tool_name in capabilities.tool_names
            if tool_name in allowed_tools
        ],
    )
