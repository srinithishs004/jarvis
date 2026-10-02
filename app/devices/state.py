from app.models.device import DeviceConnection
from app.redis.store import RedisStore


class DeviceStateStore:
    PREFIX = "jarvis:device:"
    TTL_SECONDS = 90

    def __init__(
        self,
        redis: RedisStore | None = None,
        *,
        ttl_seconds: int = TTL_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        self.redis = redis or RedisStore()
        self.ttl_seconds = ttl_seconds

    def _key(self, device_id: str) -> str:
        return f"{self.PREFIX}{device_id}"

    def save(self, device: DeviceConnection) -> None:
        self.redis.set(
            self._key(device.device_id),
            device.model_dump(mode="json"),
            ttl_seconds=self.ttl_seconds,
        )

    def get(self, device_id: str) -> DeviceConnection | None:
        raw = self.redis.get(self._key(device_id))

        if raw is None:
            return None

        return DeviceConnection.model_validate(raw)

    def delete(self, device_id: str) -> None:
        self.redis.delete(self._key(device_id))
