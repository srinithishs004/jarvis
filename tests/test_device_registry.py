from datetime import datetime, timezone

import pytest

from app.devices.registry import DeviceRegistry
from app.devices.state import DeviceStateStore
from app.models.device import (
    DeviceCapabilities,
    DeviceHeartbeat,
    DeviceRegistration,
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


def make_registry():
    redis = FakeRedis()
    state = DeviceStateStore(redis)
    return DeviceRegistry(state), state


def registration(
    device_id: str = "windows-01",
) -> DeviceRegistration:
    return DeviceRegistration(
        device_id=device_id,
        device_name="JARVIS Windows",
        device_type=DeviceType.WINDOWS,
        agent_version="0.1.0",
        capabilities=DeviceCapabilities(
            capabilities=["keyboard", "mouse"],
            tool_names=["windows.keyboard"],
        ),
    )


def test_registers_device():
    registry, _ = make_registry()

    device = registry.register(registration())

    assert device.device_id == "windows-01"
    assert device.status == DeviceStatus.ONLINE
    assert device.capabilities.capabilities == ["keyboard", "mouse"]
    assert registry.exists("windows-01")


def test_reregistration_replaces_connection_state():
    registry, _ = make_registry()

    first = registry.register(registration())
    second = registry.register(
        registration("windows-01").model_copy(
            update={"agent_version": "0.2.0"}
        )
    )

    assert second.agent_version == "0.2.0"
    assert registry.get("windows-01").agent_version == "0.2.0"
    assert second.connected_at >= first.connected_at


def test_heartbeat_updates_timestamp_and_status():
    registry, _ = make_registry()
    registry.register(registration())
    registry.disconnect("windows-01")

    timestamp = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)

    device = registry.heartbeat(
        DeviceHeartbeat(
            device_id="windows-01",
            timestamp=timestamp,
        )
    )

    assert device.status == DeviceStatus.ONLINE
    assert device.last_heartbeat_at == timestamp


def test_heartbeat_requires_registered_device():
    registry, _ = make_registry()

    with pytest.raises(KeyError, match="Device not registered"):
        registry.heartbeat(
            DeviceHeartbeat(device_id="unknown")
        )


def test_disconnect_marks_device_offline():
    registry, _ = make_registry()
    registry.register(registration())

    device = registry.disconnect("windows-01")

    assert device.status == DeviceStatus.OFFLINE


def test_mark_stale_devices_marks_expired_online_devices_offline():
    registry, state = make_registry()

    device = registry.register(registration())
    device.last_heartbeat_at = datetime(
        2026, 10, 2, 18, 0, tzinfo=timezone.utc
    )
    state.save(device)

    now = datetime(2026, 10, 2, 18, 1, tzinfo=timezone.utc)

    stale = registry.mark_stale_devices(
        now=now,
        timeout_seconds=60,
    )

    assert [device.device_id for device in stale] == ["windows-01"]
    assert registry.get("windows-01").status == DeviceStatus.OFFLINE


def test_mark_stale_devices_keeps_recent_devices_online():
    registry, state = make_registry()

    device = registry.register(registration())
    device.last_heartbeat_at = datetime(
        2026, 10, 2, 18, 0, tzinfo=timezone.utc
    )
    state.save(device)

    now = datetime(2026, 10, 2, 18, 0, 30, tzinfo=timezone.utc)

    stale = registry.mark_stale_devices(
        now=now,
        timeout_seconds=60,
    )

    assert stale == []
    assert registry.get("windows-01").status == DeviceStatus.ONLINE


def test_disconnect_requires_registered_device():
    registry, _ = make_registry()

    with pytest.raises(KeyError, match="Device not registered"):
        registry.disconnect("unknown")


def test_list_and_remove_devices():
    registry, _ = make_registry()

    registry.register(registration("windows-01"))
    registry.register(registration("windows-02"))

    assert {
        device.device_id
        for device in registry.list()
    } == {"windows-01", "windows-02"}

    registry.remove("windows-01")

    assert not registry.exists("windows-01")
    assert registry.exists("windows-02")


def test_registry_loads_device_from_persistent_state():
    _, state = make_registry()

    first_registry = DeviceRegistry(state)
    first_registry.register(registration())

    second_registry = DeviceRegistry(state)

    device = second_registry.get("windows-01")

    assert device.device_id == "windows-01"
    assert device.status == DeviceStatus.ONLINE
