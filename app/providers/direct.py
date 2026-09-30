import os
from typing import Any

import httpx

from app.models.provider import (
    ModelProviderError,
    ModelRequest,
    ModelResponse,
)
from app.providers.base import ModelProvider


class OpenAIProvider(ModelProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "OpenAIProvider":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "OPENAI_BASE_URL",
                "https://api.openai.com/v1",
            ),
            default_model=os.getenv("OPENAI_MODEL"),
            timeout_seconds=float(
                os.getenv("OPENAI_TIMEOUT_SECONDS", "60")
            ),
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self.default_model
        if not model:
            raise ModelProviderError(
                "No OpenAI model specified. Set OPENAI_MODEL or "
                "provide ModelRequest.model."
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

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"OpenAI request failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise ModelProviderError(
                "OpenAI returned invalid JSON"
            ) from exc

        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content", "")
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError(
                "OpenAI returned an invalid chat response"
            ) from exc

        return ModelResponse(
            provider=self.name,
            model=data.get("model", model),
            content=content,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage", {}),
            raw=data,
        )


class AnthropicProvider(ModelProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        default_model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "AnthropicProvider":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")

        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "ANTHROPIC_BASE_URL",
                "https://api.anthropic.com",
            ),
            default_model=os.getenv("ANTHROPIC_MODEL"),
            timeout_seconds=float(
                os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "60")
            ),
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self.default_model
        if not model:
            raise ModelProviderError(
                "No Anthropic model specified. Set ANTHROPIC_MODEL or "
                "provide ModelRequest.model."
            )

        system_messages = [
            message.content
            for message in request.messages
            if message.role == "system"
        ]

        messages = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in request.messages
            if message.role != "system"
        ]

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_tokens or 4096,
            "messages": messages,
        }

        if system_messages:
            payload["system"] = "\n\n".join(system_messages)

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            response = httpx.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"Anthropic request failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise ModelProviderError(
                "Anthropic returned invalid JSON"
            ) from exc

        try:
            content_blocks = data["content"]
            content = "".join(
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise ModelProviderError(
                "Anthropic returned an invalid message response"
            ) from exc

        return ModelResponse(
            provider=self.name,
            model=data.get("model", model),
            content=content,
            finish_reason=data.get("stop_reason"),
            usage=data.get("usage", {}),
            raw=data,
        )
