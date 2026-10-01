from datetime import datetime, timezone

import pytest

from app.models.session import SessionContext, SessionMessage
from app.redis.session_state import SessionContextStore


class FakeRedis:
    def __init__(self) -> None:
        self.data = {}

    def set(self, key, value, ttl_seconds=None):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        self.data.pop(key, None)


def test_session_create_and_get():
    store = SessionContextStore(FakeRedis())

    context = store.create("session-1")

    assert context.session_id == "session-1"
    assert context.messages == []

    loaded = store.get("session-1")

    assert loaded == context


def test_session_append_preserves_message_order():
    store = SessionContextStore(FakeRedis())

    store.append(
        "session-1",
        role="user",
        content="Hello",
    )
    store.append(
        "session-1",
        role="assistant",
        content="Hi there",
    )

    context = store.get("session-1")

    assert context is not None
    assert context.messages == [
        SessionMessage(role="user", content="Hello"),
        SessionMessage(role="assistant", content="Hi there"),
    ]


def test_session_history_is_bounded():
    store = SessionContextStore(
        FakeRedis(),
        max_messages=3,
    )

    for index in range(5):
        store.append(
            "session-1",
            role="user",
            content=f"message-{index}",
        )

    context = store.get("session-1")

    assert context is not None
    assert [message.content for message in context.messages] == [
        "message-2",
        "message-3",
        "message-4",
    ]


def test_missing_session_is_created_on_append():
    store = SessionContextStore(FakeRedis())

    context = store.append(
        "new-session",
        role="user",
        content="First message",
    )

    assert context.session_id == "new-session"
    assert len(context.messages) == 1


def test_session_delete():
    store = SessionContextStore(FakeRedis())

    store.create("session-1")
    assert store.get("session-1") is not None

    store.delete("session-1")

    assert store.get("session-1") is None


@pytest.mark.parametrize(
    ("ttl_seconds", "max_messages"),
    [
        (0, 20),
        (-1, 20),
        (86400, 0),
        (86400, -1),
    ],
)
def test_session_store_rejects_invalid_limits(
    ttl_seconds,
    max_messages,
):
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        SessionContextStore(
            FakeRedis(),
            ttl_seconds=ttl_seconds,
            max_messages=max_messages,
        )
