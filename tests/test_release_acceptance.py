from app.core.response_engine import ResponseEngine, ResponseMode
from app.models.agent import AgentDecision, AgentDecisionType
from app.models.tool import PermissionLevel
from app.tools.builtin import register_builtin_tools
from app.tools.registry import ToolRegistry


def test_release_surface_contains_only_supported_builtin_tool():
    registry = ToolRegistry()
    register_builtin_tools(registry)

    tools = registry.list()

    assert [tool.name for tool in tools] == ["system.health"]

    tool = tools[0]
    assert tool.permission == PermissionLevel.L0
    assert tool.requires_confirmation is False
    assert callable(tool.handler)


def test_release_response_modes_are_deterministic():
    engine = ResponseEngine()
    decision = AgentDecision(
        type=AgentDecisionType.RESPOND,
        content="JARVIS online.",
    )

    for mode in ResponseMode:
        if mode == ResponseMode.SILENT:
            assert engine.render(decision, mode=mode) == ""
        else:
            assert engine.render(decision, mode=mode) == "JARVIS online."


def test_release_tool_failure_messages_are_deterministic():
    engine = ResponseEngine()
    decision = AgentDecision(
        type=AgentDecisionType.TOOL_CALL,
        content=None,
        tool_call={"tool_name": "system.health", "arguments": {}},
    )

    assert (
        engine.render(
            decision,
            {"ok": False, "error_type": "confirmation_required"},
        )
        == "Confirmation required."
    )

    assert (
        engine.render(
            decision,
            {"ok": False, "error_type": "kill_switch_active"},
        )
        == "JARVIS kill switch is active."
    )

    assert (
        engine.render(
            decision,
            {"ok": False, "error_type": "tool_not_found"},
        )
        == "I couldn't find that tool."
    )


def test_release_acceptance_document_exists():
    from pathlib import Path

    document = Path(__file__).parents[1] / "docs" / "release-1-acceptance.md"

    assert document.is_file()
    text = document.read_text()

    required_sections = [
        "# JARVIS OS — Release 1 Acceptance Contract",
        "## Capability matrix",
        "## Release acceptance criteria",
        "## Explicitly deferred",
    ]

    for section in required_sections:
        assert section in text
