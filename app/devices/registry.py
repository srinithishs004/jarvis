from datetime import datetime, timezone

from app.devices.state import DeviceStateStore
from app.models.device import (
    DeviceCapabilities,
    DeviceConnection,
    DeviceHeartbeat,
    DeviceRegistration,
    DeviceStatus,
)


class DeviceRegistry:
    """Registry of currently known device connections."""

    def __init__(
        self,
        state_store: DeviceStateStore | None = None,
    ) -> None:
        self.state_store = state_store or DeviceStateStore()
        self._devices: dict[str, DeviceConnection] = {}

    def register(self, registration: DeviceRegistration) -> DeviceConnection:
        now = datetime.now(timezone.utc)

        connection = DeviceConnection(
            device_id=registration.device_id,
            device_name=registration.device_name,
            device_type=registration.device_type,
            agent_version=registration.agent_version,
            capabilities=registration.capabilities,
            status=DeviceStatus.ONLINE,
            connected_at=now,
            last_heartbeat_at=now,
        )

        self._devices[registration.device_id] = connection
        self.state_store.save(connection)
        return connection

    def heartbeat(self, heartbeat: DeviceHeartbeat) -> DeviceConnection:
        device = self.get(heartbeat.device_id)

        device.last_heartbeat_at = heartbeat.timestamp
        device.status = DeviceStatus.ONLINE

        self._devices[device.device_id] = device
        self.state_store.save(device)
        return device

    def disconnect(self, device_id: str) -> DeviceConnection:
        device = self.get(device_id)

        device.status = DeviceStatus.OFFLINE

        self._devices[device_id] = device
        self.state_store.save(device)
        return device

    def update_capabilities(
        self,
        device_id: str,
        capabilities: DeviceCapabilities,
    ) -> DeviceConnection:
        device = self.get(device_id)

        device.capabilities = capabilities

        self._devices[device_id] = device
        self.state_store.save(device)
        return device

    def get(self, device_id: str) -> DeviceConnection:
        device = self._devices.get(device_id)

        if device is not None:
            return device

        device = self.state_store.get(device_id)

        if device is None:
            raise KeyError(f"Device not registered: {device_id}")

        self._devices[device_id] = device
        return device

    def list(self) -> list[DeviceConnection]:
        return list(self._devices.values())

    def exists(self, device_id: str) -> bool:
        return self._devices.get(device_id) is not None or (
            self.state_store.get(device_id) is not None
        )

    def remove(self, device_id: str) -> None:
        self._devices.pop(device_id, None)
        self.state_store.delete(device_id)
