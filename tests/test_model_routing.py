import pytest

from app.models.provider import (
    ModelRequest,
    ModelResponse,
    ModelRouteError,
    ProviderNotFoundError,
)
from app.providers.base import ModelProvider
from app.providers.registry import ModelProviderRegistry
from app.providers.router import ModelRoute, ModelRouter


class FakeProvider(ModelProvider):
    name = "fake"

    def __init__(self):
        self.requests = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)

        return ModelResponse(
            provider=self.name,
            model=request.model or "unknown",
            content="fake response",
        )


def make_router():
    provider = FakeProvider()

    registry = ModelProviderRegistry()
    registry.register(provider)

    router = ModelRouter(
        registry=registry,
        default_route="local",
    )

    router.register_route(
        ModelRoute(
            name="local",
            provider="fake",
            model="fake-model",
        )
    )

    return router, provider


def test_provider_registry_registers_and_resolves():
    provider = FakeProvider()
    registry = ModelProviderRegistry()

    registry.register(provider)

    assert registry.exists("fake")
    assert registry.get("fake") is provider
    assert registry.list() == [provider]


def test_provider_registry_rejects_duplicates():
    provider = FakeProvider()
    registry = ModelProviderRegistry()

    registry.register(provider)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(provider)


def test_provider_registry_reports_missing_provider():
    registry = ModelProviderRegistry()

    with pytest.raises(
        ProviderNotFoundError,
        match="not found",
    ):
        registry.get("missing")


def test_router_selects_provider_and_model():
    router, provider = make_router()

    response = router.generate(
        ModelRequest(
            messages=[
                {
                    "role": "user",
                    "content": "hello",
                }
            ]
        )
    )

    assert response.content == "fake response"
    assert response.provider == "fake"
    assert response.model == "fake-model"

    assert len(provider.requests) == 1
    assert provider.requests[0].model == "fake-model"


def test_request_model_overrides_route_model():
    router, provider = make_router()

    router.generate(
        ModelRequest(
            model="override-model",
            messages=[
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
        )
    )

    assert provider.requests[0].model == "override-model"


def test_router_supports_explicit_route():
    router, provider = make_router()

    router.register_route(
        ModelRoute(
            name="alternate",
            provider="fake",
            model="alternate-model",
        )
    )

    response = router.generate(
        ModelRequest(
            messages=[
                {
                    "role": "user",
                    "content": "hello",
                }
            ]
        ),
        route="alternate",
    )

    assert response.model == "alternate-model"


def test_router_rejects_unknown_route():
    router, _ = make_router()

    with pytest.raises(ModelRouteError, match="not found"):
        router.generate(
            ModelRequest(
                messages=[
                    {
                        "role": "user",
                        "content": "hello",
                    }
                ]
            ),
            route="missing",
        )


def test_route_cannot_use_unknown_provider():
    registry = ModelProviderRegistry()
    router = ModelRouter(
        registry=registry,
        default_route="default",
    )

    with pytest.raises(ModelRouteError, match="not registered"):
        router.register_route(
            ModelRoute(
                name="default",
                provider="missing",
                model="some-model",
            )
        )


def test_factory_builds_legacy_default_route(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.setenv("MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("MODEL_NAME", "qwen3:4b")
    monkeypatch.setenv("MODEL_ROUTE", "default")
    monkeypatch.setenv(
        "MODEL_BASE_URL",
        "http://127.0.0.1:11434/v1",
    )

    router = create_model_router()

    route = router.get_route()

    assert route.name == "default"
    assert route.provider == "openai-compatible"
    assert route.model == "qwen3:4b"


def test_factory_builds_local_routes(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("LOCAL_MODEL_NAME", "qwen3:1.7b")
    monkeypatch.setenv("LOCAL_SMART_MODEL_NAME", "qwen3:4b")
    monkeypatch.setenv("MODEL_ROUTE", "local-smart")

    router = create_model_router()

    assert router.get_route("local-fast").model == "qwen3:1.7b"
    assert router.get_route("local-smart").model == "qwen3:4b"
    assert router.get_route().name == "local-smart"


def test_factory_builds_openrouter_route(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv(
        "OPENROUTER_MODEL",
        "qwen/qwen3-4b:free",
    )
    monkeypatch.setenv("MODEL_ROUTE", "openrouter")

    router = create_model_router()

    route = router.get_route()

    assert route.name == "openrouter"
    assert route.provider == "openrouter"
    assert route.model == "qwen/qwen3-4b:free"


def test_factory_builds_openai_route(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-openai-model")
    monkeypatch.setenv("MODEL_ROUTE", "openai")

    router = create_model_router()

    route = router.get_route()

    assert route.name == "openai"
    assert route.provider == "openai"
    assert route.model == "test-openai-model"


def test_factory_builds_anthropic_route(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv(
        "ANTHROPIC_MODEL",
        "test-anthropic-model",
    )
    monkeypatch.setenv("MODEL_ROUTE", "anthropic")

    router = create_model_router()

    route = router.get_route()

    assert route.name == "anthropic"
    assert route.provider == "anthropic"
    assert route.model == "test-anthropic-model"


def test_factory_builds_gemini_route(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-gemini-model")
    monkeypatch.setenv("MODEL_ROUTE", "gemini")

    router = create_model_router()

    route = router.get_route()

    assert route.name == "gemini"
    assert route.provider == "gemini"
    assert route.model == "test-gemini-model"


def test_factory_ignores_unconfigured_providers(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("LOCAL_MODEL_NAME", "qwen3:1.7b")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("MODEL_ROUTE", "local-fast")

    router = create_model_router()

    assert [route.name for route in router.routes()] == [
        "local-fast",
    ]


def test_factory_rejects_unavailable_default_route(monkeypatch):
    from app.providers.factory import create_model_router

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("LOCAL_MODEL_NAME", "qwen3:1.7b")
    monkeypatch.setenv("MODEL_ROUTE", "does-not-exist")

    with pytest.raises(ValueError, match="not available"):
        create_model_router()


def test_factory_requires_at_least_one_model_route(monkeypatch):
    from app.providers.factory import create_model_router

    for key in (
        "MODEL_NAME",
        "MODEL_PROVIDER",
        "LOCAL_MODEL_NAME",
        "LOCAL_SMART_MODEL_NAME",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValueError, match="No model routes configured"):
        create_model_router()
