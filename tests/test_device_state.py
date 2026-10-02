from datetime import datetime, timezone

from app.devices.state import DeviceStateStore
from app.models.device import (
    DeviceCapabilities,
    DeviceConnection,
    DeviceStatus,
    DeviceType,
)


class FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, key, value, *, ttl_seconds):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)


def device() -> DeviceConnection:
    timestamp = datetime(
        2026,
        10,
        2,
        18,
        0,
        tzinfo=timezone.utc,
    )

    return DeviceConnection(
        device_id="windows-01",
        device_name="JARVIS Windows",
        device_type=DeviceType.WINDOWS,
        agent_version="0.1.0",
        capabilities=DeviceCapabilities(
            capabilities=["keyboard"],
            tool_names=["windows.keyboard"],
        ),
        status=DeviceStatus.ONLINE,
        connected_at=timestamp,
        last_heartbeat_at=timestamp,
    )


def test_device_state_round_trip():
    redis = FakeRedis()
    store = DeviceStateStore(redis)

    original = device()
    store.save(original)

    restored = store.get("windows-01")

    assert restored == original


def test_device_state_delete():
    redis = FakeRedis()
    store = DeviceStateStore(redis)

    store.save(device())
    store.delete("windows-01")

    assert store.get("windows-01") is None


def test_device_state_uses_device_prefix():
    redis = FakeRedis()
    store = DeviceStateStore(redis)

    store.save(device())

    assert "jarvis:device:windows-01" in redis.values
