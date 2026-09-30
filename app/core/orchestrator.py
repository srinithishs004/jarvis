import json
from typing import Any

from app.models.agent import (
    AgentDecision,
    AgentDecisionType,
    AgentToolCall,
)
from app.models.provider import ModelMessage, ModelRequest
from app.providers.router import ModelRouter
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter


class Orchestrator:
    """
    Converts a user request into a validated agent decision.

    The orchestrator may ask a model to decide what should happen,
    but it never executes model output directly. Tool execution must
    pass through ToolRouter.
    """

    def __init__(
        self,
        model_router: ModelRouter,
        tool_registry: ToolRegistry,
        tool_router: ToolRouter,
    ) -> None:
        self.model_router = model_router
        self.tool_registry = tool_registry
        self.tool_router = tool_router

    def decide(
        self,
        user_input: str,
        *,
        route: str | None = None,
    ) -> AgentDecision:
        if not user_input.strip():
            return AgentDecision(
                type=AgentDecisionType.CLARIFY,
                question="What would you like JARVIS to do?",
            )

        request = ModelRequest(
            messages=[
                ModelMessage(
                    role="system",
                    content=self._system_prompt(),
                ),
                ModelMessage(
                    role="user",
                    content=user_input,
                ),
            ],
        )

        response = self.model_router.generate(request, route=route)

        return self._parse_decision(response.content)

    def execute_tool_call(
        self,
        decision: AgentDecision,
    ) -> dict[str, Any]:
        """
        Execute only a validated TOOL_CALL decision.

        ToolRouter remains the sole execution boundary for permissions,
        confirmations, task persistence, cancellation and kill switch.
        """
        if decision.type != AgentDecisionType.TOOL_CALL:
            raise ValueError("Decision is not a tool call")

        if decision.tool_call is None:
            raise ValueError("Tool call decision is missing tool_call")

        tool_call: AgentToolCall = decision.tool_call

        if not self.tool_registry.exists(tool_call.tool_name):
            return {
                "ok": False,
                "error": f"Tool not found: {tool_call.tool_name}",
                "error_type": "tool_not_found",
            }

        return self.tool_router.execute(
            tool_call.tool_name,
            arguments=tool_call.arguments,
        )

    @staticmethod
    def _system_prompt() -> str:
        return """
You are the decision engine for JARVIS.

Return exactly one JSON object.

Allowed decision types:

1. respond
{
  "type": "respond",
  "content": "..."
}

2. tool_call
{
  "type": "tool_call",
  "tool_call": {
    "tool_name": "...",
    "arguments": {}
  }
}

3. plan
{
  "type": "plan",
  "plan": ["step 1", "step 2"]
}

4. clarify
{
  "type": "clarify",
  "question": "..."
}

Rules:
- Never invent tool names.
- Never include executable code as a substitute for a tool call.
- Use tool_call only when an available tool is appropriate.
- Do not claim that a tool was executed.
- Do not perform actions yourself.
- Return JSON only.
""".strip()

    @staticmethod
    def _parse_decision(content: str) -> AgentDecision:
        raw = content.strip()

        # Accept fenced JSON from models that ignore the JSON-only instruction.
        if raw.startswith("```"):
            lines = raw.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            raw = "\n".join(lines).strip()

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Model returned invalid agent decision JSON"
            ) from exc

        decision = AgentDecision.model_validate(payload)

        if decision.type == AgentDecisionType.TOOL_CALL:
            if decision.tool_call is None:
                raise ValueError(
                    "Tool-call decision must contain tool_call"
                )

        return decision
