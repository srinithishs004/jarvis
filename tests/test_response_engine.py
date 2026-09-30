from app.core.response_engine import ResponseEngine, ResponseMode
from app.models.agent import AgentDecision, AgentDecisionType


def test_respond_decision_returns_content():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.RESPOND,
        content="Hello.",
    )

    assert engine.render(decision) == "Hello."


def test_clarify_decision_returns_question():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.CLARIFY,
        question="Which device?",
    )

    assert engine.render(decision) == "Which device?"


def test_tool_success_is_concise():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.TOOL_CALL,
    )

    execution = {
        "ok": True,
        "tool": "system.health",
        "task_id": "abc",
        "status": "succeeded",
    }

    assert engine.render(
        decision,
        execution,
        mode=ResponseMode.SHORT,
    ) == "Done."


def test_queued_tool_reports_started():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.TOOL_CALL,
    )

    execution = {
        "ok": True,
        "tool": "example",
        "task_id": "abc",
        "status": "queued",
    }

    assert engine.render(
        decision,
        execution,
        mode=ResponseMode.SHORT,
    ) == "Task started."


def test_confirmation_required_is_explicit():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.TOOL_CALL,
    )

    execution = {
        "ok": False,
        "tool": "dangerous.tool",
        "error_type": "confirmation_required",
        "requires_confirmation": True,
    }

    assert engine.render(decision, execution) == "Confirmation required."


def test_cancellation_is_explicit():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.TOOL_CALL,
    )

    execution = {
        "ok": False,
        "tool": "example",
        "error_type": "cancelled",
    }

    assert engine.render(decision, execution) == "Task cancelled."


def test_silent_mode_returns_empty_string():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.RESPOND,
        content="This should not be spoken.",
    )

    assert engine.render(
        decision,
        mode=ResponseMode.SILENT,
    ) == ""


def test_detailed_tool_result_contains_task_id():
    engine = ResponseEngine()

    decision = AgentDecision(
        type=AgentDecisionType.TOOL_CALL,
    )

    execution = {
        "ok": True,
        "tool": "system.health",
        "task_id": "abc123",
        "status": "succeeded",
        "result": {"status": "healthy"},
    }

    result = engine.render(
        decision,
        execution,
        mode=ResponseMode.DETAILED,
    )

    assert "Completed successfully." in result
    assert "system.health" in result
    assert "abc123" in result
