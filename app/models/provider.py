from typing import Any

from pydantic import BaseModel, Field


class ModelMessage(BaseModel):
    role: str = Field(min_length=1)
    content: str


class ModelRequest(BaseModel):
    messages: list[ModelMessage] = Field(min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    provider: str
    model: str
    content: str
    finish_reason: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: Any = None


class ModelProviderError(RuntimeError):
    """Base error raised by a model provider."""


class ProviderNotFoundError(ModelProviderError):
    pass


class ModelRouteError(ModelProviderError):
    pass
