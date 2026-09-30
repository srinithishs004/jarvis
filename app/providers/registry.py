from app.models.provider import ProviderNotFoundError
from app.providers.base import ModelProvider


class ModelProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        if not provider.name:
            raise ValueError("Provider name cannot be empty")

        if provider.name in self._providers:
            raise ValueError(
                f"Provider already registered: {provider.name}"
            )

        self._providers[provider.name] = provider

    def get(self, name: str) -> ModelProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise ProviderNotFoundError(
                f"Model provider not found: {name}"
            ) from None

    def exists(self, name: str) -> bool:
        return name in self._providers

    def list(self) -> list[ModelProvider]:
        return list(self._providers.values())
