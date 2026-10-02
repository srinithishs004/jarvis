import asyncio

from app.devices.auth import DeviceAuthenticator
from app.devices.connection import DeviceConnectionManager
from app.devices.registry import DeviceRegistry
from app.devices.state import DeviceStateStore
from app.devices.websocket import handle_device_websocket


class FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, *, ttl_seconds):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)


class FakeWebSocket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent = []
        self.closed = False
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        if not self.incoming:
            raise RuntimeError("test websocket exhausted")
        value = self.incoming.pop(0)

        if isinstance(value, BaseException):
            raise value

        return value

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self, code=None):
        self.closed = True


def make_manager():
    redis = FakeRedis()
    state = DeviceStateStore(redis)
    registry = DeviceRegistry(state)
    return DeviceConnectionManager(registry)


def hello(auth, device_id="windows-01"):
    from app.models.device import (
        DeviceCapabilities,
        DeviceRegistration,
        DeviceType,
    )

    registration = DeviceRegistration(
        device_id=device_id,
        device_name="JARVIS Windows",
        device_type=DeviceType.WINDOWS,
        agent_version="0.1.0",
        capabilities=DeviceCapabilities(
            capabilities=["keyboard"],
            tool_names=["windows.keyboard"],
        ),
    )

    return {
        "type": "hello",
        "registration": registration.model_dump(mode="json"),
        "token": auth.create_token(device_id),
    }


def test_rejects_non_hello_first_message():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    websocket = FakeWebSocket([
        {"type": "heartbeat"},
    ])

    asyncio.run(
        handle_device_websocket(
            websocket,
            connection_manager=manager,
            authenticator=auth,
        )
    )

    assert websocket.accepted is True
    assert websocket.closed is True
    assert websocket.sent[0]["type"] == "error"
    assert websocket.sent[0]["code"] == "authentication_required"
    assert not manager.connected("windows-01")


def test_rejects_invalid_authentication():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    message = hello(auth)
    message["token"] = "invalid"

    websocket = FakeWebSocket([message])

    asyncio.run(
        handle_device_websocket(
            websocket,
            connection_manager=manager,
            authenticator=auth,
        )
    )

    assert websocket.closed is True
    assert websocket.sent[0]["code"] == "authentication_failed"
    assert not manager.connected("windows-01")


def test_registers_authenticated_device():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    websocket = FakeWebSocket([
        hello(auth),
        RuntimeError("stop"),
    ])

    try:
        asyncio.run(
            handle_device_websocket(
                websocket,
                connection_manager=manager,
                authenticator=auth,
            )
        )
    except RuntimeError:
        pass

    assert websocket.accepted is True
    assert websocket.sent[0] == {
        "type": "ack",
        "request_type": "hello",
    }
    assert manager.registry.exists("windows-01")


def test_heartbeat_requires_matching_device_id():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    websocket = FakeWebSocket([
        hello(auth),
        {
            "type": "heartbeat",
            "heartbeat": {
                "device_id": "windows-02",
            },
        },
        RuntimeError("stop"),
    ])

    try:
        asyncio.run(
            handle_device_websocket(
                websocket,
                connection_manager=manager,
                authenticator=auth,
            )
        )
    except RuntimeError:
        pass

    assert any(
        message.get("code") == "device_id_mismatch"
        for message in websocket.sent
    )


def test_unknown_message_is_rejected():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    websocket = FakeWebSocket([
        hello(auth),
        {"type": "something_unknown"},
        RuntimeError("stop"),
    ])

    try:
        asyncio.run(
            handle_device_websocket(
                websocket,
                connection_manager=manager,
                authenticator=auth,
            )
        )
    except RuntimeError:
        pass

    assert any(
        message.get("code") == "unknown_message_type"
        for message in websocket.sent
    )


def test_capabilities_update_succeeds():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    websocket = FakeWebSocket([
        hello(auth),
        {
            "type": "capabilities",
            "device_id": "windows-01",
            "capabilities": {
                "capabilities": ["keyboard", "mouse"],
                "tool_names": ["windows.keyboard", "windows.mouse"],
            },
        },
        RuntimeError("stop"),
    ])

    try:
        asyncio.run(
            handle_device_websocket(
                websocket,
                connection_manager=manager,
                authenticator=auth,
            )
        )
    except RuntimeError:
        pass

    assert websocket.sent[1] == {
        "type": "ack",
        "request_type": "capabilities",
    }
    device = manager.registry.get("windows-01")
    assert device.capabilities.tool_names == [
        "windows.keyboard",
        "windows.mouse",
    ]


def test_malformed_heartbeat_returns_error_and_connection_continues():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    websocket = FakeWebSocket([
        hello(auth),
        {
            "type": "heartbeat",
            "heartbeat": {},
        },
        {"type": "something_unknown"},
        RuntimeError("stop"),
    ])

    try:
        asyncio.run(
            handle_device_websocket(
                websocket,
                connection_manager=manager,
                authenticator=auth,
            )
        )
    except RuntimeError:
        pass

    assert websocket.sent[1] == {
        "type": "error",
        "code": "invalid_message",
        "message": "Invalid heartbeat message",
    }
    assert websocket.sent[2]["code"] == "unknown_message_type"


def test_malformed_capabilities_returns_error_and_connection_continues():
    auth = DeviceAuthenticator("test-secret")
    manager = make_manager()

    websocket = FakeWebSocket([
        hello(auth),
        {
            "type": "capabilities",
            "device_id": "windows-01",
            "capabilities": {
                "capabilities": "not-a-list",
                "tool_names": [],
            },
        },
        {"type": "something_unknown"},
        RuntimeError("stop"),
    ])

    try:
        asyncio.run(
            handle_device_websocket(
                websocket,
                connection_manager=manager,
                authenticator=auth,
            )
        )
    except RuntimeError:
        pass

    assert websocket.sent[1] == {
        "type": "error",
        "code": "invalid_message",
        "message": "Invalid capabilities message",
    }
    assert websocket.sent[2]["code"] == "unknown_message_type"
