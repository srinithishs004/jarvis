import httpx
import pytest

from app.models.provider import (
    ModelMessage,
    ModelProviderError,
    ModelRequest,
)
from app.providers.direct import AnthropicProvider, OpenAIProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


class FakeHTTPResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("POST", "http://test"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


def test_openai_provider_builds_request_and_parses_response(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout

        return FakeHTTPResponse(
            {
                "id": "response-1",
                "model": "gpt-test",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "hello from openai",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                },
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = OpenAIProvider(
        api_key="test-key",
        base_url="https://openai.test/v1",
        default_model="gpt-test",
    )

    response = provider.generate(
        ModelRequest(
            messages=[
                ModelMessage(
                    role="system",
                    content="You are helpful.",
                ),
                ModelMessage(
                    role="user",
                    content="Hello",
                ),
            ],
            temperature=0.2,
            max_tokens=100,
        )
    )

    assert captured["url"] == (
        "https://openai.test/v1/chat/completions"
    )
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"] == {
        "model": "gpt-test",
        "messages": [
            {
                "role": "system",
                "content": "You are helpful.",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ],
        "temperature": 0.2,
        "max_tokens": 100,
    }

    assert response.provider == "openai"
    assert response.model == "gpt-test"
    assert response.content == "hello from openai"
    assert response.finish_reason == "stop"
    assert response.usage["prompt_tokens"] == 10


def test_openai_provider_request_model_overrides_default(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["json"] = json
        return FakeHTTPResponse(
            {
                "model": "override-model",
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = OpenAIProvider(
        api_key="test-key",
        default_model="default-model",
    )

    provider.generate(
        ModelRequest(
            model="override-model",
            messages=[
                ModelMessage(
                    role="user",
                    content="hello",
                )
            ],
        )
    )

    assert captured["json"]["model"] == "override-model"


def test_openai_provider_rejects_missing_model():
    provider = OpenAIProvider(
        api_key="test-key",
    )

    with pytest.raises(
        ModelProviderError,
        match="No OpenAI model specified",
    ):
        provider.generate(
            ModelRequest(
                messages=[
                    ModelMessage(
                        role="user",
                        content="hello",
                    )
                ]
            )
        )


def test_openai_compatible_provider_builds_request_and_parses_response(
    monkeypatch,
):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers

        return FakeHTTPResponse(
            {
                "model": "qwen3:4b",
                "choices": [
                    {
                        "message": {
                            "content": "local response",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "total_tokens": 20,
                },
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = OpenAICompatibleProvider(
        name="local",
        base_url="http://localhost:11434/v1",
        api_key="local-key",
        default_model="qwen3:4b",
    )

    response = provider.generate(
        ModelRequest(
            messages=[
                ModelMessage(
                    role="user",
                    content="hello",
                )
            ],
            temperature=0,
        )
    )

    assert captured["url"] == (
        "http://localhost:11434/v1/chat/completions"
    )
    assert captured["headers"]["Authorization"] == "Bearer local-key"
    assert captured["json"]["model"] == "qwen3:4b"
    assert captured["json"]["temperature"] == 0

    assert response.provider == "local"
    assert response.model == "qwen3:4b"
    assert response.content == "local response"
    assert response.finish_reason == "stop"


def test_openai_compatible_provider_can_omit_api_key(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["headers"] = headers

        return FakeHTTPResponse(
            {
                "model": "local-model",
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        default_model="local-model",
    )

    provider.generate(
        ModelRequest(
            messages=[
                ModelMessage(
                    role="user",
                    content="hello",
                )
            ]
        )
    )

    assert "Authorization" not in captured["headers"]


def test_anthropic_provider_builds_request_and_parses_response(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers

        return FakeHTTPResponse(
            {
                "id": "msg-test",
                "model": "claude-test",
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": "hello from claude",
                    },
                    {
                        "type": "tool_use",
                        "id": "ignored",
                    },
                ],
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 7,
                },
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    provider = AnthropicProvider(
        api_key="test-key",
        base_url="https://anthropic.test",
        default_model="claude-test",
    )

    response = provider.generate(
        ModelRequest(
            messages=[
                ModelMessage(
                    role="system",
                    content="You are helpful.",
                ),
                ModelMessage(
                    role="user",
                    content="Hello",
                ),
            ],
            temperature=0.3,
            max_tokens=200,
        )
    )

    assert captured["url"] == (
        "https://anthropic.test/v1/messages"
    )
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"

    assert captured["json"] == {
        "model": "claude-test",
        "max_tokens": 200,
        "messages": [
            {
                "role": "user",
                "content": "Hello",
            }
        ],
        "system": "You are helpful.",
        "temperature": 0.3,
    }

    assert response.provider == "anthropic"
    assert response.model == "claude-test"
    assert response.content == "hello from claude"
    assert response.finish_reason == "end_turn"
    assert response.usage["input_tokens"] == 12


def test_anthropic_provider_uses_default_max_tokens():
    provider = AnthropicProvider(
        api_key="test-key",
        default_model="claude-test",
    )

    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["json"] = json

        return FakeHTTPResponse(
            {
                "model": "claude-test",
                "content": [
                    {
                        "type": "text",
                        "text": "ok",
                    }
                ],
            }
        )

    # Patch the provider module's httpx client without making a network call.
    import app.providers.direct as direct

    original_post = direct.httpx.post
    direct.httpx.post = fake_post

    try:
        provider.generate(
            ModelRequest(
                messages=[
                    ModelMessage(
                        role="user",
                        content="hello",
                    )
                ]
            )
        )
    finally:
        direct.httpx.post = original_post

    assert captured["json"]["max_tokens"] == 4096


@pytest.mark.parametrize(
    "provider",
    [
        OpenAIProvider(
            api_key="test-key",
            default_model="test-model",
        ),
        AnthropicProvider(
            api_key="test-key",
            default_model="test-model",
        ),
    ],
)
def test_direct_providers_wrap_http_errors(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        raise httpx.ConnectError(
            "connection failed",
            request=httpx.Request("POST", "http://test"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(
        ModelProviderError,
        match="request failed",
    ):
        provider.generate(
            ModelRequest(
                messages=[
                    ModelMessage(
                        role="user",
                        content="hello",
                    )
                ]
            )
        )
