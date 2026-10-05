from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AgentConfig:
    server_url: str
    device_id: str
    device_name: str
    auth_secret: str
    agent_version: str = "0.1.0"
    heartbeat_interval_seconds: float = 20.0

    @classmethod
    def from_environment(cls) -> "AgentConfig":
        server_url = os.environ.get("JARVIS_SERVER_URL")
        device_id = os.environ.get("JARVIS_DEVICE_ID")
        device_name = os.environ.get("JARVIS_DEVICE_NAME")
        auth_secret = os.environ.get("JARVIS_DEVICE_AUTH_SECRET")

        missing = [
            name
            for name, value in (
                ("JARVIS_SERVER_URL", server_url),
                ("JARVIS_DEVICE_ID", device_id),
                ("JARVIS_DEVICE_NAME", device_name),
                ("JARVIS_DEVICE_AUTH_SECRET", auth_secret),
            )
            if not value
        ]

        if missing:
            raise ValueError(
                "Missing required environment variables: "
                + ", ".join(missing)
            )

        return cls(
            server_url=server_url,
            device_id=device_id,
            device_name=device_name,
            auth_secret=auth_secret,
        )
