import os

from app.providers.direct import AnthropicProvider, OpenAIProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.providers.registry import ModelProviderRegistry
from app.providers.router import ModelRoute, ModelRouter


def _register_openai_compatible(
    registry: ModelProviderRegistry,
    *,
    name: str,
    base_url: str,
    api_key: str | None,
) -> None:
    if not registry.exists(name):
        provider = OpenAICompatibleProvider(
            name=name,
            base_url=base_url,
            api_key=api_key,
        )
        registry.register(provider)


def create_model_router() -> ModelRouter:
    registry = ModelProviderRegistry()

    routes: list[ModelRoute] = []

    # Backward-compatible generic/local configuration.
    model_name = os.getenv("MODEL_NAME")
    model_provider = os.getenv(
        "MODEL_PROVIDER",
        "openai-compatible",
    )

    if model_provider == "openai-compatible":
        _register_openai_compatible(
            registry,
            name="openai-compatible",
            base_url=os.getenv(
                "MODEL_BASE_URL",
                "http://127.0.0.1:11434/v1",
            ),
            api_key=os.getenv("MODEL_API_KEY"),
        )

        if model_name:
            routes.append(
                ModelRoute(
                    name=os.getenv("MODEL_ROUTE", "default"),
                    provider="openai-compatible",
                    model=model_name,
                )
            )

    # Local Ollama / compatible server.
    local_model = os.getenv("LOCAL_MODEL_NAME")
    local_smart_model = os.getenv("LOCAL_SMART_MODEL_NAME")

    if local_model or local_smart_model:
        _register_openai_compatible(
            registry,
            name="openai-compatible",
            base_url=os.getenv(
                "LOCAL_MODEL_BASE_URL",
                "http://127.0.0.1:11434/v1",
            ),
            api_key=os.getenv("LOCAL_MODEL_API_KEY"),
        )

        if local_model:
            routes.append(
                ModelRoute(
                    name="local-fast",
                    provider="openai-compatible",
                    model=local_model,
                )
            )

        if local_smart_model:
            routes.append(
                ModelRoute(
                    name="local-smart",
                    provider="openai-compatible",
                    model=local_smart_model,
                )
            )

    # OpenRouter uses the OpenAI-compatible API.
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openrouter_model = os.getenv("OPENROUTER_MODEL")

    if openrouter_key and openrouter_model:
        if not registry.exists("openrouter"):
            registry.register(
                OpenAICompatibleProvider(
                    name="openrouter",
                    base_url=os.getenv(
                        "OPENROUTER_BASE_URL",
                        "https://openrouter.ai/api/v1",
                    ),
                    api_key=openrouter_key,
                )
            )

        routes.append(
            ModelRoute(
                name="openrouter",
                provider="openrouter",
                model=openrouter_model,
            )
        )

    # Native OpenAI API.
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL")

    if openai_key and openai_model:
        registry.register(OpenAIProvider.from_env())
        routes.append(
            ModelRoute(
                name="openai",
                provider="openai",
                model=openai_model,
            )
        )

    # Native Anthropic API.
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model = os.getenv("ANTHROPIC_MODEL")

    if anthropic_key and anthropic_model:
        registry.register(AnthropicProvider.from_env())
        routes.append(
            ModelRoute(
                name="anthropic",
                provider="anthropic",
                model=anthropic_model,
            )
        )

    # Gemini exposes an OpenAI-compatible endpoint.
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")

    if gemini_key and gemini_model:
        if not registry.exists("gemini"):
            registry.register(
                OpenAICompatibleProvider(
                    name="gemini",
                    base_url=os.getenv(
                        "GEMINI_BASE_URL",
                        "https://generativelanguage.googleapis.com/v1beta/openai",
                    ),
                    api_key=gemini_key,
                )
            )

        routes.append(
            ModelRoute(
                name="gemini",
                provider="gemini",
                model=gemini_model,
            )
        )

    requested_route = os.getenv("MODEL_ROUTE")

    if not routes:
        raise ValueError(
            "No model routes configured. Configure MODEL_NAME for the "
            "legacy/default route, or one of LOCAL_MODEL_NAME, "
            "OPENROUTER_MODEL, OPENAI_MODEL, ANTHROPIC_MODEL, or GEMINI_MODEL."
        )

    route_names = {route.name for route in routes}

    default_route = requested_route or routes[0].name

    if default_route not in route_names:
        raise ValueError(
            f"Configured MODEL_ROUTE '{default_route}' is not available. "
            f"Available routes: {sorted(route_names)}"
        )

    router = ModelRouter(
        registry=registry,
        routes=routes,
        default_route=default_route,
    )

    return router
