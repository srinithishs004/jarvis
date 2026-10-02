import hashlib
import hmac
import os


class DeviceAuthenticator:
    """
    Authenticates a device using a server-side shared secret.

    The raw secret is never stored in the device registry or connection state.
    """

    ENV_NAME = "JARVIS_DEVICE_AUTH_SECRET"

    def __init__(self, secret: str | None = None) -> None:
        self.secret = secret or os.environ.get(self.ENV_NAME)

        if not self.secret:
            raise ValueError(
                f"{self.ENV_NAME} must be configured"
            )

    def create_token(self, device_id: str) -> str:
        return hmac.new(
            self.secret.encode(),
            device_id.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify(self, device_id: str, token: str) -> bool:
        expected = self.create_token(device_id)

        return hmac.compare_digest(expected, token)
