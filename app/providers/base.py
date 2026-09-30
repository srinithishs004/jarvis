from abc import ABC, abstractmethod

from app.models.provider import ModelRequest, ModelResponse


class ModelProvider(ABC):
    """
    Provider-neutral model interface.

    The rest of JARVIS should depend on this interface rather than
    provider-specific SDKs or HTTP APIs.
    """

    name: str

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError
