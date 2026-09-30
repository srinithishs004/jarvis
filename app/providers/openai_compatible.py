import os
from typing import Any

import httpx

from app.models.provider import (
    ModelProviderError,
    ModelRequest,
    ModelResponse,
)
from app.providers.base import ModelProvider


class OpenAICompatibleProvider(ModelProvider):
    """
    Provider for APIs implementing the OpenAI chat-completions shape.

    This also works as the transport abstraction for local servers such
    as Ollama's OpenAI-compatible endpoint.
    """

    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "OpenAICompatibleProvider":
        return cls(
            base_url=os.getenv(
                "MODEL_BASE_URL",
                "http://127.0.0.1:11434/v1",
            ),
            api_key=os.getenv("MODEL_API_KEY"),
            default_model=os.getenv("MODEL_NAME"),
            timeout_seconds=float(
                os.getenv("MODEL_TIMEOUT_SECONDS", "60")
            ),
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self.default_model

        if not model:
            raise ModelProviderError(
                "No model specified. Set MODEL_NAME or provide "
                "ModelRequest.model."
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in request.messages
            ],
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"Model provider request failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise ModelProviderError(
                "Model provider returned invalid JSON"
            ) from exc

        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content", "")
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError(
                "Model provider returned an invalid chat response"
            ) from exc

        return ModelResponse(
            provider=self.name,
            model=data.get("model", model),
            content=content,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage", {}),
            raw=data,
        )
