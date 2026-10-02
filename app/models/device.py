from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    WINDOWS = "windows"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class DeviceCapabilities(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)


class DeviceRegistration(BaseModel):
    device_id: str = Field(min_length=1)
    device_name: str = Field(min_length=1)
    device_type: DeviceType
    agent_version: str = Field(min_length=1)
    capabilities: DeviceCapabilities = Field(
        default_factory=DeviceCapabilities
    )


class DeviceHeartbeat(BaseModel):
    device_id: str = Field(min_length=1)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DeviceConnection(BaseModel):
    device_id: str = Field(min_length=1)
    device_name: str = Field(min_length=1)
    device_type: DeviceType
    agent_version: str = Field(min_length=1)
    capabilities: DeviceCapabilities = Field(
        default_factory=DeviceCapabilities
    )
    status: DeviceStatus = DeviceStatus.ONLINE
    connected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_heartbeat_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DeviceMessage(BaseModel):
    type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
