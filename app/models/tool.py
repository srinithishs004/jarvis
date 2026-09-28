from enum import IntEnum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class PermissionLevel(IntEnum):
    L0 = 0  # Read-only
    L1 = 1  # Low-risk action
    L2 = 2  # Important action
    L3 = 3  # Dangerous/destructive action


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    permission: PermissionLevel = PermissionLevel.L0
    requires_confirmation: bool = False
    timeout_seconds: float = Field(default=30.0, gt=0)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    handler: Callable[..., Any] | None = None
