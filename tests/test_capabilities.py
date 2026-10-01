import pytest

from app.core.capabilities import register_builtin_capabilities
from app.models.capability import CapabilityStatus, ExecutionLocation
from app.models.tool import PermissionLevel, ToolDefinition
from app.tools.capability_registry import CapabilityRegistry
from app.tools.registry import ToolRegistry


def test_capability_registry_register_get_list_and_exists():
    registry = CapabilityRegistry()

    from app.models.capability import CapabilityDefinition

    capability = CapabilityDefinition(
        name="test.device",
        description="Test device",
        version="1.2.3",
        capabilities=["display", "input"],
        status=CapabilityStatus.ONLINE,
        execution_location=ExecutionLocation.REMOTE,
        tool_names=["device.display"],
    )

    registry.register(capability)

    assert registry.exists("test.device")
    assert registry.get("test.device") == capability
    assert registry.list() == [capability]


def test_capability_registry_rejects_duplicate_names():
    registry = CapabilityRegistry()

    from app.models.capability import CapabilityDefinition

    capability = CapabilityDefinition(
        name="test.device",
        description="Test device",
    )

    registry.register(capability)

    with pytest.raises(ValueError, match="Capability already registered"):
        registry.register(capability)


def test_capability_registry_rejects_unknown_capability():
    registry = CapabilityRegistry()

    with pytest.raises(KeyError, match="Capability not found"):
        registry.get("missing.device")


def test_builtin_capability_reflects_registered_tools():
    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolDefinition(
            name="device.display",
            description="Display something",
            permission=PermissionLevel.L0,
        )
    )

    capability_registry = CapabilityRegistry()
    register_builtin_capabilities(
        capability_registry,
        tool_registry,
    )

    capability = capability_registry.get("jarvis.api")

    assert capability.name == "jarvis.api"
    assert capability.version == "0.1.0"
    assert capability.status == CapabilityStatus.ONLINE
    assert capability.execution_location == ExecutionLocation.LOCAL
    assert "tool.discovery" in capability.capabilities
    assert "task.execution" in capability.capabilities
    assert capability.tool_names == ["device.display"]
