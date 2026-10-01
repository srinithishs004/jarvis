from app.models.capability import (
    CapabilityDefinition,
    CapabilityStatus,
    ExecutionLocation,
)
from app.tools.capability_registry import CapabilityRegistry
from app.tools.registry import ToolRegistry


def register_builtin_capabilities(
    registry: CapabilityRegistry,
    tool_registry: ToolRegistry,
) -> None:
    registry.register(
        CapabilityDefinition(
            name="jarvis.api",
            description="Core JARVIS API capabilities",
            version="0.1.0",
            capabilities=[
                "system.health",
                "tool.discovery",
                "task.execution",
            ],
            status=CapabilityStatus.ONLINE,
            execution_location=ExecutionLocation.LOCAL,
            tool_names=[
                tool.name
                for tool in tool_registry.list()
            ],
        )
    )
