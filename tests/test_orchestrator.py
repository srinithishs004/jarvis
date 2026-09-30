from app.core.orchestrator import Orchestrator
from app.models.agent import AgentDecisionType
from app.models.provider import ModelResponse
from app.models.tool import ToolDefinition
from app.providers.registry import ModelProviderRegistry
from app.providers.router import ModelRoute, ModelRouter
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter


class FakeProvider:
    name = "fake"

    def __init__(self, content: str):
        self.content = content

    def generate(self, request):
        return ModelResponse(
            provider=self.name,
            model="fake-model",
            content=self.content,
        )


def make_orchestrator(content: str):
    registry = ModelProviderRegistry()
    registry.register(FakeProvider(content))

    router = ModelRouter(
        registry=registry,
        routes=[
            ModelRoute(
                name="default",
                provider="fake",
                model="fake-model",
            )
        ],
        default_route="default",
    )

    tool_registry = ToolRegistry()
    tool_router = ToolRouter(tool_registry)

    return Orchestrator(
        model_router=router,
        tool_registry=tool_registry,
        tool_router=tool_router,
    )


def test_orchestrator_parses_response():
    orchestrator = make_orchestrator(
        '{"type":"respond","content":"Hello"}'
    )

    decision = orchestrator.decide("Hello")

    assert decision.type == AgentDecisionType.RESPOND
    assert decision.content == "Hello"


def test_orchestrator_parses_tool_call():
    orchestrator = make_orchestrator(
        """
        {
          "type": "tool_call",
          "tool_call": {
            "tool_name": "example",
            "arguments": {"value": 42}
          }
        }
        """
    )

    decision = orchestrator.decide("Do the thing")

    assert decision.type == AgentDecisionType.TOOL_CALL
    assert decision.tool_call is not None
    assert decision.tool_call.tool_name == "example"
    assert decision.tool_call.arguments == {"value": 42}


def test_orchestrator_parses_lfm_native_tool_call():
    orchestrator = make_orchestrator(
        "<|tool_call_start|>[system.health()]<|tool_call_end|>"
    )

    decision = orchestrator.decide("Check system health")

    assert decision.type == AgentDecisionType.TOOL_CALL
    assert decision.tool_call is not None
    assert decision.tool_call.tool_name == "system.health"
    assert decision.tool_call.arguments == {}


def test_empty_input_requests_clarification():
    orchestrator = make_orchestrator(
        '{"type":"respond","content":"should not be used"}'
    )

    decision = orchestrator.decide("   ")

    assert decision.type == AgentDecisionType.CLARIFY
    assert decision.question


def test_invalid_model_output_is_rejected():
    orchestrator = make_orchestrator("not json")

    try:
        orchestrator.decide("Do something")
    except ValueError as exc:
        assert "invalid agent decision JSON" in str(exc)
    else:
        raise AssertionError("Expected invalid model output to fail")


def test_unknown_tool_is_not_executed():
    orchestrator = make_orchestrator(
        """
        {
          "type": "tool_call",
          "tool_call": {
            "tool_name": "does_not_exist",
            "arguments": {}
          }
        }
        """
    )

    decision = orchestrator.decide("Do something")
    result = orchestrator.execute_tool_call(decision)

    assert result["ok"] is False
    assert result["error_type"] == "tool_not_found"


def orchestrator_test_handler(**kwargs):
    return {"received": kwargs}


def test_tool_call_is_sent_to_tool_router():
    calls = []

    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="test_tool",
            description="Test tool",
            handler=orchestrator_test_handler,
        )
    )

    class FakeRouter:
        def generate(self, request, route=None):
            return ModelResponse(
                provider="fake",
                model="fake",
                content=(
                    '{"type":"tool_call","tool_call":'
                    '{"tool_name":"test_tool","arguments":{"x":1}}}'
                ),
            )

    tool_router = ToolRouter(registry)

    orchestrator = Orchestrator(
        model_router=FakeRouter(),
        tool_registry=registry,
        tool_router=tool_router,
    )

    decision = orchestrator.decide("Run test tool")
    result = orchestrator.execute_tool_call(decision)

    assert result["tool"] == "test_tool"
    assert result["ok"] is True
    assert result["task_id"] is not None
