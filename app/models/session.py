from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionMessage(BaseModel):
    role: str = Field(min_length=1)
    content: str


class SessionContext(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[SessionMessage] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
