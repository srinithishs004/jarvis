import os

from dotenv import load_dotenv
from fastapi import FastAPI
import psycopg
from upstash_redis import Redis

from app.tools.builtin import register_builtin_tools
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter

from app.core.confirmation import ConfirmationManager
from app.models.task import TaskStatus

load_dotenv("/opt/jarvis/.env")

app = FastAPI(
    title="JARVIS API",
    version="0.1.0",
)

tool_registry = ToolRegistry()
register_builtin_tools(tool_registry)

confirmation_manager = ConfirmationManager()

tool_router = ToolRouter(
    tool_registry,
    confirmation_manager=confirmation_manager,
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "jarvis-api",
        "version": "0.1.0",
    }


@app.get("/health/db")
def health_db():
    database_url = os.environ["SUPABASE_DB_URL"]

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()

    return {
        "status": "ok",
        "service": "supabase-postgres",
        "result": result[0],
    }


@app.get("/health/redis")
def health_redis():
    redis = Redis(
        url=os.environ["UPSTASH_REDIS_REST_URL"],
        token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
    )

    result = redis.ping()

    return {
        "status": "ok",
        "service": "upstash-redis",
        "result": result,
    }


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "permission": tool.permission.name,
                "requires_confirmation": tool.requires_confirmation,
                "timeout_seconds": tool.timeout_seconds,
            }
            for tool in tool_registry.list()
        ]
    }

from typing import Any

from fastapi import Body

@app.post("/tools/{tool_name:path}/execute")
def execute_tool(
    tool_name: str,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    return tool_router.execute(
        tool_name,
        arguments=payload.get("arguments", {}),
        confirmation_id=payload.get("confirmation_id"),
    )

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    try:
        task = tool_router.task_manager.get(task_id)
    except KeyError:
        return {
            "ok": False,
            "error": f"Task not found: {task_id}",
            "error_type": "task_not_found",
        }

    return {
        "ok": True,
        "task": {
            "task_id": task.task_id,
            "tool_name": task.tool_name,
            "status": task.status.value,
            "confirmation_id": task.confirmation_id,
            "result": task.result,
            "error": task.error,
            "error_type": task.error_type,
            "created_at": task.created_at.isoformat(),
            "started_at": (
                task.started_at.isoformat()
                if task.started_at
                else None
            ),
            "completed_at": (
                task.completed_at.isoformat()
                if task.completed_at
                else None
            ),
            "cancel_requested": task.cancel_requested,
        },
    }


@app.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    try:
        task = tool_router.task_manager.request_cancel(task_id)
    except KeyError:
        return {
            "ok": False,
            "error": f"Task not found: {task_id}",
            "error_type": "task_not_found",
        }
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "error_type": "task_not_cancellable",
        }

    return {
        "ok": True,
        "task_id": task.task_id,
        "status": task.status.value,
        "cancel_requested": task.cancel_requested,
    }


@app.post("/confirmations/{confirmation_id}/approve")
def approve_confirmation(confirmation_id: str):
    approved = confirmation_manager.approve(confirmation_id)

    return {
        "approved": approved,
        "confirmation_id": confirmation_id,
    }
