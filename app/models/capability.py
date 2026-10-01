from enum import Enum

from pydantic import BaseModel, Field


class ExecutionLocation(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class CapabilityStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class CapabilityDefinition(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    version: str = Field(default="1.0.0", min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    status: CapabilityStatus = CapabilityStatus.ONLINE
    execution_location: ExecutionLocation = ExecutionLocation.LOCAL
    tool_names: list[str] = Field(default_factory=list)
