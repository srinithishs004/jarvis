import os

from app.providers.openai_compatible import OpenAICompatibleProvider
from app.providers.registry import ModelProviderRegistry
from app.providers.router import ModelRoute, ModelRouter


def create_model_router() -> ModelRouter:
    registry = ModelProviderRegistry()

    provider_name = os.getenv(
        "MODEL_PROVIDER",
        "openai-compatible",
    )

    if provider_name == "openai-compatible":
        registry.register(
            OpenAICompatibleProvider.from_env()
        )
    else:
        raise ValueError(
            f"Unsupported MODEL_PROVIDER: {provider_name}"
        )

    model = os.getenv("MODEL_NAME")

    if not model:
        raise ValueError(
            "MODEL_NAME must be configured"
        )

    route_name = os.getenv("MODEL_ROUTE", "default")

    router = ModelRouter(
        registry=registry,
        default_route=route_name,
    )

    router.register_route(
        ModelRoute(
            name=route_name,
            provider=provider_name,
            model=model,
        )
    )

    return router
