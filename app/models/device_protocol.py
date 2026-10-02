from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.device import (
    DeviceCapabilities,
    DeviceHeartbeat,
    DeviceRegistration,
)


class DeviceHello(BaseModel):
    type: Literal["hello"] = "hello"
    registration: DeviceRegistration


class DeviceHeartbeatMessage(BaseModel):
    type: Literal["heartbeat"] = "heartbeat"
    heartbeat: DeviceHeartbeat


class DeviceCapabilitiesMessage(BaseModel):
    type: Literal["capabilities"] = "capabilities"
    device_id: str = Field(min_length=1)
    capabilities: DeviceCapabilities


class DeviceAck(BaseModel):
    type: Literal["ack"] = "ack"
    request_type: str = Field(min_length=1)


class DeviceError(BaseModel):
    type: Literal["error"] = "error"
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class DeviceCommand(BaseModel):
    type: Literal["command"] = "command"
    request_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class DeviceCommandResult(BaseModel):
    type: Literal["command_result"] = "command_result"
    request_id: str = Field(min_length=1)
    success: bool
    result: Any = None
    error: str | None = None
