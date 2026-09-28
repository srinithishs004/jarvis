import json
import os
from typing import Any

import psycopg

from app.models.task import Task


class TaskRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ["SUPABASE_DB_URL"]

    def create(self, task: Task) -> None:
        metadata = {
            "tool_name": task.tool_name,
            "arguments": task.arguments,
            "confirmation_id": task.confirmation_id,
            "result": task.result,
            "error": task.error,
            "error_type": task.error_type,
            "cancel_requested": task.cancel_requested,
            "started_at": (
                task.started_at.isoformat()
                if task.started_at
                else None
            ),
        }

        with psycopg.connect(self.database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tasks (
                        id,
                        title,
                        status,
                        completed_at,
                        metadata,
                        created_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::jsonb,
                        %s
                    )
                    """,
                    (
                        task.task_id,
                        f"Execute: {task.tool_name}",
                        task.status.value,
                        task.completed_at,
                        json.dumps(metadata, default=str),
                        task.created_at,
                    ),
                )
            conn.commit()

    def update(self, task: Task) -> None:
        metadata = {
            "tool_name": task.tool_name,
            "arguments": task.arguments,
            "confirmation_id": task.confirmation_id,
            "result": task.result,
            "error": task.error,
            "error_type": task.error_type,
            "cancel_requested": task.cancel_requested,
            "started_at": (
                task.started_at.isoformat()
                if task.started_at
                else None
            ),
        }

        with psycopg.connect(self.database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tasks
                    SET
                        status = %s,
                        completed_at = %s,
                        metadata = %s::jsonb,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        task.status.value,
                        task.completed_at,
                        json.dumps(metadata, default=str),
                        task.task_id,
                    ),
                )
            conn.commit()
