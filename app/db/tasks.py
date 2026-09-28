import json
import os
from datetime import datetime
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


    def get(self, task_id: str) -> Task | None:
        with psycopg.connect(self.database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        status,
                        completed_at,
                        created_at,
                        metadata
                    FROM tasks
                    WHERE id = %s
                    """,
                    (task_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None

        task_id_db, status, completed_at, created_at, metadata = row
        metadata = metadata or {}

        started_at = metadata.get("started_at")
        if started_at:
            from datetime import datetime
            started_at = datetime.fromisoformat(started_at)

        return Task(
            task_id=str(task_id_db),
            tool_name=metadata.get("tool_name", ""),
            arguments=metadata.get("arguments", {}),
            status=status,
            confirmation_id=metadata.get("confirmation_id"),
            result=metadata.get("result"),
            error=metadata.get("error"),
            error_type=metadata.get("error_type"),
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            cancel_requested=metadata.get("cancel_requested", False),
        )

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

    def list_active(self) -> list[Task]:
        with psycopg.connect(self.database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        status,
                        completed_at,
                        created_at,
                        metadata
                    FROM tasks
                    WHERE status IN ('queued', 'running')
                    ORDER BY created_at ASC
                    """
                )
                rows = cur.fetchall()

        tasks: list[Task] = []

        for (
            task_id_db,
            status,
            completed_at,
            created_at,
            metadata,
        ) in rows:
            metadata = metadata or {}

            started_at = metadata.get("started_at")
            if started_at:
                started_at = datetime.fromisoformat(started_at)

            tasks.append(
                Task(
                    task_id=str(task_id_db),
                    tool_name=metadata.get("tool_name", ""),
                    arguments=metadata.get("arguments", {}),
                    status=status,
                    confirmation_id=metadata.get("confirmation_id"),
                    result=metadata.get("result"),
                    error=metadata.get("error"),
                    error_type=metadata.get("error_type"),
                    created_at=created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    cancel_requested=metadata.get(
                        "cancel_requested",
                        False,
                    ),
                )
            )

        return tasks
