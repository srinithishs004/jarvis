import asyncio

import pytest

from app.devices.auth import DeviceAuthenticator
from app.devices.connection import DeviceConnectionManager
from app.devices.registry import DeviceRegistry
from app.devices.state import DeviceStateStore


class FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, *, ttl_seconds):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)


def make_manager():
    redis = FakeRedis()
    state = DeviceStateStore(redis)
    registry = DeviceRegistry(state)
    return DeviceConnectionManager(registry)


class FakeWebSocket:
    def __init__(self):
        self.messages = []
        self.closed = False

    async def send_json(self, message):
        self.messages.append(message)

    async def close(self):
        self.closed = True


def test_authentication_token_round_trip():
    auth = DeviceAuthenticator("test-secret")

    token = auth.create_token("windows-01")

    assert auth.verify("windows-01", token)
    assert not auth.verify("windows-02", token)
    assert not auth.verify("windows-01", "invalid")


def test_authentication_does_not_expose_secret():
    auth = DeviceAuthenticator("test-secret")

    token = auth.create_token("windows-01")

    assert "test-secret" not in repr(token)


def test_authentication_requires_secret():
    with pytest.raises(ValueError, match="JARVIS_DEVICE_AUTH_SECRET"):
        DeviceAuthenticator("")


def test_connection_manager_attach_and_send():
    manager = make_manager()
    websocket = FakeWebSocket()

    asyncio.run(manager.attach("windows-01", websocket))

    assert manager.connected("windows-01")
    assert manager.list_connected() == ["windows-01"]

    sent = asyncio.run(
        manager.send(
            "windows-01",
            {"type": "ack", "request_type": "hello"},
        )
    )

    assert sent is True
    assert websocket.messages == [
        {"type": "ack", "request_type": "hello"}
    ]


def test_connection_manager_send_unknown_device():
    manager = make_manager()

    sent = asyncio.run(
        manager.send(
            "unknown",
            {"type": "ack"},
        )
    )

    assert sent is False


def test_connection_manager_detach_and_close():
    manager = make_manager()
    websocket = FakeWebSocket()

    asyncio.run(manager.attach("windows-01", websocket))

    asyncio.run(manager.close("windows-01"))

    assert not manager.connected("windows-01")
    assert websocket.closed is True


def test_connection_manager_replaces_existing_connection():
    manager = make_manager()
    first = FakeWebSocket()
    second = FakeWebSocket()

    asyncio.run(manager.attach("windows-01", first))
    asyncio.run(manager.attach("windows-01", second))

    assert first.closed is True
    assert manager.get("windows-01") is second


def test_connection_manager_old_socket_cannot_detach_replacement():
    manager = make_manager()
    first = FakeWebSocket()
    second = FakeWebSocket()

    asyncio.run(manager.attach("windows-01", first))
    asyncio.run(manager.attach("windows-01", second))

    manager.detach("windows-01", first)

    assert manager.connected("windows-01")
    assert manager.get("windows-01") is second
