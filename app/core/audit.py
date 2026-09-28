from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AuditEvent:
    event_type: str
    tool_name: str
    success: bool
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    permission_level: str | None = None
    confirmation_id: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error_type: str | None = None
    duration_ms: float | None = None


class AuditLogger:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    def list_events(self) -> list[AuditEvent]:
        return list(self._events)
