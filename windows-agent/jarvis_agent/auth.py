import hashlib
import hmac


def create_device_token(device_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode(),
        device_id.encode(),
        hashlib.sha256,
    ).hexdigest()
