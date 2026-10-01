from datetime import datetime, timezone

from app.models.session import SessionContext, SessionMessage
from app.redis.store import RedisStore


class SessionContextStore:
    PREFIX = "jarvis:session:"
    DEFAULT_TTL_SECONDS = 86400
    DEFAULT_MAX_MESSAGES = 20

    def __init__(
        self,
        redis: RedisStore | None = None,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_messages <= 0:
            raise ValueError("max_messages must be greater than zero")

        self.redis = redis or RedisStore()
        self.ttl_seconds = ttl_seconds
        self.max_messages = max_messages

    def _key(self, session_id: str) -> str:
        return f"{self.PREFIX}{session_id}"

    def create(self, session_id: str | None = None) -> SessionContext:
        context = SessionContext(
            session_id=session_id or SessionContext().session_id,
        )
        self.save(context)
        return context

    def get(self, session_id: str) -> SessionContext | None:
        raw = self.redis.get(self._key(session_id))

        if raw is None:
            return None

        return SessionContext.model_validate(raw)

    def save(self, context: SessionContext) -> None:
        context.updated_at = datetime.now(timezone.utc)

        self.redis.set(
            self._key(context.session_id),
            context.model_dump(mode="json"),
            ttl_seconds=self.ttl_seconds,
        )

    def append(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
    ) -> SessionContext:
        context = self.get(session_id)

        if context is None:
            context = self.create(session_id)

        context.messages.append(
            SessionMessage(
                role=role,
                content=content,
            )
        )

        context.messages = context.messages[-self.max_messages:]
        self.save(context)

        return context

    def delete(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id))
