import json
import os
from typing import Any

import psycopg

from app.core.audit import AuditEvent


class AuditRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ["SUPABASE_DB_URL"]

    def record(self, event: AuditEvent) -> None:
        details: dict[str, Any] = {
            "permission_level": event.permission_level,
            "confirmation_id": event.confirmation_id,
            "arguments": event.arguments,
            "result": event.result,
            "error_type": event.error_type,
            "duration_ms": event.duration_ms,
        }

        with psycopg.connect(self.database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_events (
                        event_type,
                        actor_type,
                        action,
                        resource_type,
                        resource_id,
                        success,
                        details,
                        created_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::jsonb,
                        %s
                    )
                    """,
                    (
                        event.event_type,
                        "jarvis",
                        event.tool_name,
                        "tool",
                        event.tool_name,
                        event.success,
                        json.dumps(details, default=str),
                        event.timestamp,
                    ),
                )
            conn.commit()
