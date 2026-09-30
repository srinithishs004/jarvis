from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentDecisionType(str, Enum):
    RESPOND = "respond"
    TOOL_CALL = "tool_call"
    PLAN = "plan"
    CLARIFY = "clarify"


class AgentToolCall(BaseModel):
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentDecision(BaseModel):
    type: AgentDecisionType
    content: str | None = None
    tool_call: AgentToolCall | None = None
    plan: list[str] = Field(default_factory=list)
    question: str | None = None
    reasoning: str | None = None
