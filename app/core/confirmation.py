from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4


@dataclass
class ConfirmationRequest:
    confirmation_id: str
    tool_name: str
    created_at: datetime
    expires_at: datetime
    approved: bool = False


class ConfirmationManager:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl_seconds = ttl_seconds
        self._requests: dict[str, ConfirmationRequest] = {}

    def create(self, tool_name: str) -> ConfirmationRequest:
        now = datetime.now(timezone.utc)

        request = ConfirmationRequest(
            confirmation_id=str(uuid4()),
            tool_name=tool_name,
            created_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )

        self._requests[request.confirmation_id] = request
        return request

    def approve(self, confirmation_id: str) -> bool:
        request = self._requests.get(confirmation_id)

        if request is None:
            return False

        if datetime.now(timezone.utc) >= request.expires_at:
            del self._requests[confirmation_id]
            return False

        request.approved = True
        return True

    def is_approved(self, confirmation_id: str, tool_name: str) -> bool:
        request = self._requests.get(confirmation_id)

        if request is None:
            return False

        if request.tool_name != tool_name:
            return False

        if datetime.now(timezone.utc) >= request.expires_at:
            del self._requests[confirmation_id]
            return False

        return request.approved
