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
