from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

from app.devices.registry import DeviceRegistry


@dataclass
class DeviceConnectionManager:
    registry: DeviceRegistry

    def __init__(
        self,
        registry: DeviceRegistry | None = None,
    ) -> None:
        self.registry = registry or DeviceRegistry()
        self._connections: dict[str, WebSocket] = {}

    async def attach(self, device_id: str, websocket: WebSocket) -> None:
        previous = self._connections.get(device_id)

        if previous is not None and previous is not websocket:
            try:
                await previous.close()
            except Exception:
                pass

        self._connections[device_id] = websocket

    def detach(self, device_id: str, websocket: WebSocket | None = None) -> None:
        current = self._connections.get(device_id)

        if current is None:
            return

        if websocket is not None and current is not websocket:
            return

        self._connections.pop(device_id, None)

    def connected(self, device_id: str) -> bool:
        return device_id in self._connections

    def get(self, device_id: str) -> WebSocket | None:
        return self._connections.get(device_id)

    async def send(
        self,
        device_id: str,
        message: dict[str, Any],
    ) -> bool:
        websocket = self.get(device_id)

        if websocket is None:
            return False

        await websocket.send_json(message)
        return True

    async def close(self, device_id: str) -> None:
        websocket = self.get(device_id)

        if websocket is None:
            return

        self.detach(device_id)
        await websocket.close()

    def list_connected(self) -> list[str]:
        return list(self._connections)
