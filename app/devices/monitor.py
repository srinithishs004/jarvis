import asyncio

from app.devices.connection import DeviceConnectionManager


class DeviceLifecycleMonitor:
    def __init__(
        self,
        connection_manager: DeviceConnectionManager,
        *,
        timeout_seconds: float = 60.0,
        interval_seconds: float = 10.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        self.connection_manager = connection_manager
        self.timeout_seconds = timeout_seconds
        self.interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()

    async def check_once(self) -> list[str]:
        stale_devices = self.connection_manager.registry.mark_stale_devices(
            timeout_seconds=self.timeout_seconds,
        )

        closed: list[str] = []

        for device in stale_devices:
            if self.connection_manager.connected(device.device_id):
                await self.connection_manager.close(device.device_id)
                closed.append(device.device_id)

        return closed

    async def run(self) -> None:
        while not self._stop_event.is_set():
            await self.check_once()

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        self._stop_event.set()
