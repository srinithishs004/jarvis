from dataclasses import dataclass

from app.models.tool import PermissionLevel, ToolDefinition


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str


class PermissionEngine:
    def evaluate(self, tool: ToolDefinition) -> PermissionDecision:
        if tool.requires_confirmation:
            return PermissionDecision(
                allowed=False,
                requires_confirmation=True,
                reason="Tool requires explicit confirmation",
            )

        if tool.permission >= PermissionLevel.L2:
            return PermissionDecision(
                allowed=False,
                requires_confirmation=True,
                reason=f"Permission level {tool.permission.name} requires confirmation",
            )

        return PermissionDecision(
            allowed=True,
            requires_confirmation=False,
            reason=f"Permission level {tool.permission.name} may execute",
        )
