from enum import Enum
from typing import Any

from app.models.agent import AgentDecision, AgentDecisionType


class ResponseMode(str, Enum):
    ULTRA_SHORT = "ultra_short"
    SHORT = "short"
    NORMAL = "normal"
    DETAILED = "detailed"
    SILENT = "silent"


class ResponseEngine:
    """
    Converts validated agent decisions and tool outcomes into
    user-facing responses.

    This class has no tool execution authority.
    """

    def render(
        self,
        decision: AgentDecision,
        execution: dict[str, Any] | None = None,
        *,
        mode: ResponseMode = ResponseMode.NORMAL,
    ) -> str:
        if mode == ResponseMode.SILENT:
            return ""

        if decision.type == AgentDecisionType.RESPOND:
            return decision.content or ""

        if decision.type == AgentDecisionType.CLARIFY:
            return decision.question or "What would you like JARVIS to do?"

        if decision.type == AgentDecisionType.PLAN:
            return self._render_plan(decision, mode)

        if decision.type == AgentDecisionType.TOOL_CALL:
            return self._render_tool_result(execution, mode)

        return "I couldn't determine what to do."

    @staticmethod
    def _render_plan(
        decision: AgentDecision,
        mode: ResponseMode,
    ) -> str:
        if not decision.plan:
            return "I need more information before proceeding."

        if mode == ResponseMode.ULTRA_SHORT:
            return "Plan ready."

        if mode == ResponseMode.SHORT:
            return "Plan ready: " + "; ".join(decision.plan)

        if mode == ResponseMode.DETAILED:
            lines = ["Here's the plan:"]
            lines.extend(
                f"{index}. {step}"
                for index, step in enumerate(decision.plan, start=1)
            )
            return "\n".join(lines)

        return "Plan ready:\n" + "\n".join(
            f"{index}. {step}"
            for index, step in enumerate(decision.plan, start=1)
        )

    @staticmethod
    def _render_tool_result(
        execution: dict[str, Any] | None,
        mode: ResponseMode,
    ) -> str:
        if execution is None:
            return "No execution result was returned."

        ok = execution.get("ok", False)
        error_type = execution.get("error_type")
        status = execution.get("status")

        if ok:
            if status == "queued":
                if mode == ResponseMode.ULTRA_SHORT:
                    return "Started."
                if mode == ResponseMode.SHORT:
                    return "Task started."
                if mode == ResponseMode.DETAILED:
                    task_id = execution.get("task_id")
                    if task_id:
                        return f"Task started successfully. Task ID: {task_id}."
                    return "Task started successfully."
                return "Task started."

            if mode == ResponseMode.ULTRA_SHORT:
                return "Done."

            if mode == ResponseMode.SHORT:
                return "Done."

            if mode == ResponseMode.DETAILED:
                tool = execution.get("tool")
                task_id = execution.get("task_id")

                details = ["Completed successfully."]
                if tool:
                    details.append(f"Tool: {tool}.")
                if task_id:
                    details.append(f"Task ID: {task_id}.")
                if "result" in execution and execution["result"] is not None:
                    details.append(f"Result: {execution['result']}")
                return " ".join(details)

            return "Done."

        messages = {
            "confirmation_required": "Confirmation required.",
            "kill_switch_active": "JARVIS kill switch is active.",
            "queue_full": "I couldn't start the task because the task queue is full.",
            "cancelled": "Task cancelled.",
            "timeout": "The task timed out.",
            "tool_not_found": "I couldn't find that tool.",
            "missing_handler": "That tool is not currently executable.",
            "execution_error": "The task failed during execution.",
        }

        message = messages.get(
            error_type,
            execution.get("error") or "The task failed.",
        )

        if mode == ResponseMode.ULTRA_SHORT:
            if error_type == "confirmation_required":
                return "Confirmation required."
            if error_type == "cancelled":
                return "Cancelled."
            return "Failed."

        if mode == ResponseMode.DETAILED:
            error = execution.get("error")
            if error and error != message:
                return f"{message} {error}"
            return message

        return message
