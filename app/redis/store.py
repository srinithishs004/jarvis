import json
import os
from typing import Any

import httpx


class RedisStore:
    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
    ) -> None:
        self.url = url or os.environ["UPSTASH_REDIS_REST_URL"]
        self.token = token or os.environ["UPSTASH_REDIS_REST_TOKEN"]

    def _request(self, command: list[Any]) -> Any:
        response = httpx.post(
            self.url,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
            json=command,
            timeout=5.0,
        )
        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        return data.get("result")

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        encoded = json.dumps(value, default=str)

        if ttl_seconds is None:
            self._request(["SET", key, encoded])
        else:
            self._request(
                ["SET", key, encoded, "EX", ttl_seconds]
            )

    def get(self, key: str) -> Any | None:
        result = self._request(["GET", key])

        if result is None:
            return None

        return json.loads(result)

    def delete(self, key: str) -> None:
        self._request(["DEL", key])

    def exists(self, key: str) -> bool:
        return bool(self._request(["EXISTS", key]))

    def scan(self, cursor: int = 0, match: str | None = None, count: int | None = None) -> tuple[int, list[str]]:
        command: list[Any] = ["SCAN", cursor]

        if match is not None:
            command.extend(["MATCH", match])

        if count is not None:
            command.extend(["COUNT", count])

        result = self._request(command)

        if not isinstance(result, list) or len(result) != 2:
            raise RuntimeError("Invalid Redis SCAN response")

        next_cursor, keys = result

        try:
            next_cursor = int(next_cursor)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Invalid Redis SCAN cursor") from exc

        if not isinstance(keys, list):
            raise RuntimeError("Invalid Redis SCAN keys")

        return next_cursor, [str(key) for key in keys]
