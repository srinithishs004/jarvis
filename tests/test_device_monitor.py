import asyncio
from datetime import datetime, timezone

from app.devices.connection import DeviceConnectionManager
from app.devices.monitor import DeviceLifecycleMonitor
from app.devices.registry import DeviceRegistry
from app.devices.state import DeviceStateStore
from app.models.device import (
    DeviceCapabilities,
    DeviceHeartbeat,
    DeviceRegistration,
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


class FakeWebSocket:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def make_manager():
    redis = FakeRedis()
    state = DeviceStateStore(redis)
    registry = DeviceRegistry(state)
    return DeviceConnectionManager(registry)


def registration() -> DeviceRegistration:
    return DeviceRegistration(
        device_id="windows-01",
        device_name="JARVIS Windows",
        device_type=DeviceType.WINDOWS,
        agent_version="0.1.0",
        capabilities=DeviceCapabilities(),
    )


def test_check_once_closes_stale_connected_device():
    manager = make_manager()
    websocket = FakeWebSocket()

    manager.registry.register(registration())
    device = manager.registry.get("windows-01")
    device.last_heartbeat_at = datetime(
        2026, 10, 2, 18, 0, tzinfo=timezone.utc
    )
    manager.registry.state_store.save(device)

    asyncio.run(manager.attach("windows-01", websocket))

    monitor = DeviceLifecycleMonitor(
        manager,
        timeout_seconds=60,
    )

    closed = asyncio.run(monitor.check_once())

    assert closed == ["windows-01"]
    assert websocket.closed is True
    assert not manager.connected("windows-01")
    assert manager.registry.get("windows-01").status.value == "offline"


def test_check_once_does_not_close_recent_device():
    manager = make_manager()
    websocket = FakeWebSocket()

    manager.registry.register(registration())
    device = manager.registry.get("windows-01")
    device.last_heartbeat_at = datetime(
        2026, 10, 2, 18, 0, tzinfo=timezone.utc
    )
    manager.registry.state_store.save(device)

    asyncio.run(manager.attach("windows-01", websocket))

    monitor = DeviceLifecycleMonitor(
        manager,
        timeout_seconds=60,
    )

    # The monitor's real clock is used by check_once, so this device's
    # timestamp is deliberately refreshed immediately before the check.
    manager.registry.heartbeat(
        DeviceHeartbeat(device_id="windows-01"),
    )

    closed = asyncio.run(monitor.check_once())

    assert closed == []
    assert websocket.closed is False
    assert manager.connected("windows-01")


def test_monitor_stop_ends_run_loop():
    manager = make_manager()
    monitor = DeviceLifecycleMonitor(
        manager,
        interval_seconds=60,
    )

    async def run_monitor():
        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0)
        monitor.stop()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(run_monitor())


def test_monitor_rejects_invalid_intervals():
    manager = make_manager()

    for kwargs in (
        {"timeout_seconds": 0},
        {"timeout_seconds": -1},
        {"interval_seconds": 0},
        {"interval_seconds": -1},
    ):
        try:
            DeviceLifecycleMonitor(manager, **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"Expected ValueError for {kwargs}")
