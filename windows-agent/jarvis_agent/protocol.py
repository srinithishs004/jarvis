from typing import Any


def make_hello(
    *,
    device_id: str,
    device_name: str,
    agent_version: str,
    token: str,
) -> dict[str, Any]:
    return {
        "type": "hello",
        "token": token,
        "registration": {
            "device_id": device_id,
            "device_name": device_name,
            "device_type": "windows",
            "agent_version": agent_version,
            "capabilities": {
                "capabilities": [
                    "windows.system.info",
                ],
                "tool_names": [
                    "windows.system.info",
                ],
            },
        },
    }


def make_heartbeat(device_id: str) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "type": "heartbeat",
        "heartbeat": {
            "device_id": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def make_command_result(
    *,
    request_id: str,
    success: bool,
    result: Any = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "command_result",
        "request_id": request_id,
        "success": success,
        "result": result,
        "error": error,
    }
