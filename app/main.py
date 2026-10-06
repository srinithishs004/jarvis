import asyncio
import hashlib
import json
import os

from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import psycopg
from upstash_redis import Redis

from app.tools.builtin import register_builtin_tools
from app.core.capabilities import register_builtin_capabilities
from app.tools.capability_registry import CapabilityRegistry
from app.tools.registry import ToolRegistry
from app.tools.router import ToolRouter

from app.core.confirmation import ConfirmationManager
from app.models.task import TaskStatus
from app.core.orchestrator import Orchestrator
from app.providers.factory import create_model_router

from app.core.response_engine import ResponseEngine, ResponseMode
from app.redis.session_state import SessionContextStore
from app.backup.factory import create_backup_service
from app.backup.service import BackupError
from app.devices.auth import DeviceAuthenticator
from app.devices.connection import DeviceConnectionManager
from app.devices.commands import DeviceCommandService
from app.devices.monitor import DeviceLifecycleMonitor
from app.core.remote_executor import RemoteToolExecutor
from app.devices.tools import (
    make_windows_app_close_tool,
    make_windows_app_launch_tool,
    make_windows_app_list_tool,
    make_windows_system_info_tool,
    make_windows_window_focus_tool,
    make_windows_keyboard_type_tool,
    make_windows_keyboard_press_tool,
    make_windows_mouse_move_tool,
    make_windows_mouse_click_tool,
)
from app.devices.websocket import handle_device_websocket

load_dotenv("/opt/jarvis/.env")

@asynccontextmanager
async def lifespan(app: FastAPI):
    reconciliation = tool_router.task_manager.reconcile_active_tasks()
    print(
        "Task reconciliation:",
        reconciliation,
    )

    tool_router.worker_pool.start()

    device_lifecycle_monitor = DeviceLifecycleMonitor(
        device_connection_manager,
        timeout_seconds=float(
            os.getenv("JARVIS_DEVICE_HEARTBEAT_TIMEOUT_SECONDS", "60")
        ),
        interval_seconds=float(
            os.getenv("JARVIS_DEVICE_HEARTBEAT_CHECK_INTERVAL_SECONDS", "10")
        ),
    )
    device_monitor_task = asyncio.create_task(
        device_lifecycle_monitor.run()
    )

    recovered = tool_router.recover_queued_tasks()
    print(
        "Queued task recovery:",
        {"recovered": recovered},
    )

    try:
        yield
    finally:
        device_lifecycle_monitor.stop()
        await device_monitor_task
        tool_router.worker_pool.shutdown()


app = FastAPI(
    title="JARVIS API",
    version="0.1.0",
    lifespan=lifespan,
)

tool_registry = ToolRegistry()
register_builtin_tools(tool_registry)

confirmation_manager = ConfirmationManager()

device_connection_manager = DeviceConnectionManager()
device_command_service = DeviceCommandService(device_connection_manager)
remote_tool_executor = RemoteToolExecutor(device_command_service)

tool_router = ToolRouter(
    tool_registry,
    confirmation_manager=confirmation_manager,
    remote_executor=remote_tool_executor,
)

for windows_tool in (
    make_windows_system_info_tool(),
    make_windows_app_list_tool(),
    make_windows_app_launch_tool(),
    make_windows_app_close_tool(),
    make_windows_window_focus_tool(),
    make_windows_keyboard_type_tool(),
    make_windows_keyboard_press_tool(),
    make_windows_mouse_move_tool(),
    make_windows_mouse_click_tool(),
):
    tool_registry.register(windows_tool)

model_router = create_model_router()

orchestrator = Orchestrator(
    model_router=model_router,
    tool_registry=tool_registry,
    tool_router=tool_router,
)

response_engine = ResponseEngine()
session_store = SessionContextStore()
backup_service = create_backup_service()

capability_registry = CapabilityRegistry()
register_builtin_capabilities(capability_registry, tool_registry)

@app.websocket("/ws/devices")
async def device_websocket(websocket: WebSocket):
    try:
        authenticator = DeviceAuthenticator()
    except ValueError:
        await websocket.accept()
        await websocket.close(code=1011)
        return

    await handle_device_websocket(
        websocket,
        connection_manager=device_connection_manager,
        authenticator=authenticator,
        command_service=device_command_service,
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


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    route: str | None = None
    response_mode: ResponseMode = ResponseMode.NORMAL


@app.post("/backup/export")
def backup_export():
    backup = backup_service.create_backup()

    return {
        "ok": True,
        "backup": backup.model_dump(mode="json"),
    }


@app.post("/backup/restore/prepare")
def backup_restore_prepare(payload: dict):
    backup_payload = payload.get("backup")

    if not isinstance(backup_payload, str):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Backup payload must be a JSON string",
                "error_type": "invalid_backup",
            },
        )

    try:
        backup = backup_service.deserialize(backup_payload)
    except BackupError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(exc),
                "error_type": "invalid_backup",
            },
        )

    try:
        canonical_payload = json.dumps(
            json.loads(backup_payload),
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Backup payload must contain valid JSON",
                "error_type": "invalid_backup",
            },
        )

    context = hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()

    request = confirmation_manager.create(
        "backup.restore",
        context=context,
    )

    return {
        "ok": True,
        "requires_confirmation": True,
        "confirmation_id": request.confirmation_id,
        "expires_at": request.expires_at.isoformat(),
        "manifest": backup.manifest.model_dump(mode="json"),
    }


@app.post("/backup/restore")
def backup_restore(payload: dict):
    backup_payload = payload.get("backup")
    confirmation_id = payload.get("confirmation_id")

    if not isinstance(backup_payload, str):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Backup payload must be a JSON string",
                "error_type": "invalid_backup",
            },
        )

    if not isinstance(confirmation_id, str) or not confirmation_id:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Backup restore confirmation is required",
                "error_type": "confirmation_required",
            },
        )

    try:
        backup = backup_service.deserialize(backup_payload)
    except BackupError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(exc),
                "error_type": "invalid_backup",
            },
        )

    try:
        canonical_payload = json.dumps(
            json.loads(backup_payload),
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Backup payload must contain valid JSON",
                "error_type": "invalid_backup",
            },
        )

    context = hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()

    if not confirmation_manager.is_approved(
        confirmation_id,
        "backup.restore",
        context=context,
        consume=True,
    ):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Backup restore confirmation is required",
                "error_type": "confirmation_required",
            },
        )

    try:
        backup_service.restore(backup)
    except BackupError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(exc),
                "error_type": "restore_failed",
            },
        )

    return {
        "ok": True,
        "restored": True,
        "manifest": backup.manifest.model_dump(mode="json"),
    }


@app.post("/chat")
def chat(payload: ChatRequest):
    context = (
        session_store.get(payload.session_id)
        if payload.session_id
        else session_store.create()
    )

    decision = orchestrator.decide(
        payload.message,
        route=payload.route,
        history=context.messages,
    )

    response = {
        "ok": True,
        "session_id": context.session_id,
        "decision": decision.model_dump(mode="json"),
    }

    execution = None

    if decision.type.value == "tool_call":
        execution = orchestrator.execute_tool_call(decision)
        response["execution"] = execution
        response["ok"] = execution.get("ok", False)

    response["message"] = response_engine.render(
        decision,
        execution,
        mode=payload.response_mode,
    )

    session_store.append(
        context.session_id,
        role="user",
        content=payload.message,
    )
    session_store.append(
        context.session_id,
        role="assistant",
        content=response["message"],
    )

    return response

@app.get("/capabilities")
def list_capabilities():
    return {
        "capabilities": [
            capability.model_dump(mode="json")
            for capability in capability_registry.list()
        ]
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
