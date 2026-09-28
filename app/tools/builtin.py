from app.models.tool import PermissionLevel, ToolDefinition
from app.tools.registry import ToolRegistry


def health_handler() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "jarvis-api",
    }


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="system.health",
            description="Check the health of the JARVIS API",
            permission=PermissionLevel.L0,
            handler=health_handler,
        )
    )
