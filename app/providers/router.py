import os
from dataclasses import dataclass

from app.models.provider import ModelRequest, ModelResponse, ModelRouteError
from app.providers.registry import ModelProviderRegistry


@dataclass(frozen=True)
class ModelRoute:
    name: str
    provider: str
    model: str


class ModelRouter:
    """
    Selects a logical model route and delegates execution to a provider.

    Routing policy is intentionally simple for now:
        route -> provider + model

    More advanced routing can later consider task type, latency,
    cost, context length, availability, or fallback providers without
    changing callers.
    """

    def __init__(
        self,
        registry: ModelProviderRegistry,
        routes: list[ModelRoute] | None = None,
        default_route: str | None = None,
    ) -> None:
        self.registry = registry
        self._routes = {
            route.name: route
            for route in (routes or [])
        }

        self.default_route = (
            default_route
            or os.getenv("MODEL_ROUTE")
            or "default"
        )

    def register_route(self, route: ModelRoute) -> None:
        if route.name in self._routes:
            raise ValueError(
                f"Model route already registered: {route.name}"
            )

        if not self.registry.exists(route.provider):
            raise ModelRouteError(
                f"Cannot register route '{route.name}': "
                f"provider '{route.provider}' is not registered"
            )

        self._routes[route.name] = route

    def get_route(self, name: str | None = None) -> ModelRoute:
        route_name = name or self.default_route

        try:
            return self._routes[route_name]
        except KeyError:
            raise ModelRouteError(
                f"Model route not found: {route_name}"
            ) from None

    def generate(
        self,
        request: ModelRequest,
        *,
        route: str | None = None,
    ) -> ModelResponse:
        selected = self.get_route(route)
        provider = self.registry.get(selected.provider)

        routed_request = request.model_copy(
            update={"model": request.model or selected.model}
        )

        return provider.generate(routed_request)

    def routes(self) -> list[ModelRoute]:
        return list(self._routes.values())
