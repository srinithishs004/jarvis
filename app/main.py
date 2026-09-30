import os

from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import FastAPI
import psycopg
from upstash_redis import Redis

from app.tools.builtin import register_builtin_tools
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter

from app.core.confirmation import ConfirmationManager
from app.models.task import TaskStatus

load_dotenv("/opt/jarvis/.env")

@asynccontextmanager
async def lifespan(app: FastAPI):
    reconciliation = tool_router.task_manager.reconcile_active_tasks()
    print(
        "Task reconciliation:",
        reconciliation,
    )

    tool_router.worker_pool.start()

    recovered = tool_router.recover_queued_tasks()
    print(
        "Queued task recovery:",
        {"recovered": recovered},
    )

    try:
        yield
    finally:
        tool_router.worker_pool.shutdown()


app = FastAPI(
    title="JARVIS API",
    version="0.1.0",
    lifespan=lifespan,
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

@app.post("/tools/{tool_name:path}/execute-async")
def execute_tool_async(
    tool_name: str,
    payload: dict[str, Any] = Body(default_factory=dict),
):
    return tool_router.execute_background(
        tool_name,
        arguments=payload.get("arguments", {}),
        confirmation_id=payload.get("confirmation_id"),
    )


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

@app.post("/tasks/kill-switch")
def activate_kill_switch():
    cancelled = tool_router.task_manager.activate_kill_switch()

    return {
        "ok": True,
        "active": True,
        "cancelled": cancelled,
        "message": "JARVIS kill switch activated",
    }


@app.delete("/tasks/kill-switch")
def deactivate_kill_switch():
    tool_router.task_manager.deactivate_kill_switch()

    return {
        "ok": True,
        "active": False,
        "message": "JARVIS kill switch deactivated",
    }


@app.get("/tasks/kill-switch")
def get_kill_switch():
    active = tool_router.task_manager.is_kill_switch_active()

    return {
        "ok": True,
        "active": active,
    }


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


@app.post("/tasks/cancel-all")
def cancel_all_tasks():
    cancelled = tool_router.task_manager.cancel_all_active()

    return {
        "ok": True,
        "cancelled": cancelled,
        "message": "Global task cancellation requested",
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
