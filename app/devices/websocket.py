from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.devices.auth import DeviceAuthenticator
from app.devices.capabilities import sanitize_device_capabilities
from app.devices.connection import DeviceConnectionManager
from app.devices.commands import DeviceCommandService
from app.models.device_protocol import (
    DeviceAck,
    DeviceCapabilitiesMessage,
    DeviceCommandResult,
    DeviceError,
    DeviceHeartbeatMessage,
    DeviceHello,
)


async def handle_device_websocket(
    websocket: WebSocket,
    *,
    connection_manager: DeviceConnectionManager,
    authenticator: DeviceAuthenticator,
    command_service: DeviceCommandService | None = None,
) -> None:
    await websocket.accept()

    device_id: str | None = None

    try:
        raw = await websocket.receive_json()

        if not isinstance(raw, dict):
            await websocket.send_json(
                DeviceError(
                    code="invalid_message",
                    message="Message must be a JSON object",
                ).model_dump()
            )
            await websocket.close(code=1008)
            return

        if raw.get("type") != "hello":
            await websocket.send_json(
                DeviceError(
                    code="authentication_required",
                    message="First message must be hello",
                ).model_dump()
            )
            await websocket.close(code=1008)
            return

        try:
            hello = DeviceHello.model_validate(raw)
        except ValidationError:
            await websocket.send_json(
                DeviceError(
                    code="invalid_message",
                    message="Invalid hello message",
                ).model_dump()
            )
            await websocket.close(code=1008)
            return
        registration = hello.registration.model_copy(
            update={
                "capabilities": sanitize_device_capabilities(
                    hello.registration.device_type,
                    hello.registration.capabilities,
                )
            }
        )
        device_id = registration.device_id

        token = raw.get("token")

        if not isinstance(token, str) or not authenticator.verify(
            device_id,
            token,
        ):
            await websocket.send_json(
                DeviceError(
                    code="authentication_failed",
                    message="Device authentication failed",
                ).model_dump()
            )
            await websocket.close(code=1008)
            return

        connection_manager.registry.register(registration)
        await connection_manager.attach(device_id, websocket)

        await websocket.send_json(
            DeviceAck(
                request_type="hello",
            ).model_dump()
        )

        while True:
            raw = await websocket.receive_json()

            if not isinstance(raw, dict):
                await websocket.send_json(
                    DeviceError(
                        code="invalid_message",
                        message="Message must be a JSON object",
                    ).model_dump()
                )
                continue

            message_type = raw.get("type")

            if message_type == "heartbeat":
                try:
                    message = DeviceHeartbeatMessage.model_validate(raw)
                except ValidationError:
                    await websocket.send_json(
                        DeviceError(
                            code="invalid_message",
                            message="Invalid heartbeat message",
                        ).model_dump()
                    )
                    continue

                if message.heartbeat.device_id != device_id:
                    await websocket.send_json(
                        DeviceError(
                            code="device_id_mismatch",
                            message="Heartbeat device_id does not match connection",
                        ).model_dump()
                    )
                    continue

                connection_manager.registry.heartbeat(
                    message.heartbeat
                )

                await websocket.send_json(
                    DeviceAck(
                        request_type="heartbeat",
                    ).model_dump()
                )
                continue

            if message_type == "command_result":
                try:
                    message = DeviceCommandResult.model_validate(raw)
                except ValidationError:
                    await websocket.send_json(
                        DeviceError(
                            code="invalid_message",
                            message="Invalid command result message",
                        ).model_dump()
                    )
                    continue

                if command_service is not None:
                    command_service.handle_result(message)

                continue

            if message_type == "capabilities":
                try:
                    message = DeviceCapabilitiesMessage.model_validate(raw)
                except ValidationError:
                    await websocket.send_json(
                        DeviceError(
                            code="invalid_message",
                            message="Invalid capabilities message",
                        ).model_dump()
                    )
                    continue

                if message.device_id != device_id:
                    await websocket.send_json(
                        DeviceError(
                            code="device_id_mismatch",
                            message="Capabilities device_id does not match connection",
                        ).model_dump()
                    )
                    continue

                connection_manager.registry.update_capabilities(
                    device_id,
                    sanitize_device_capabilities(
                        connection_manager.registry.get(device_id).device_type,
                        message.capabilities,
                    ),
                )

                await websocket.send_json(
                    DeviceAck(
                        request_type="capabilities",
                    ).model_dump()
                )
                continue

            await websocket.send_json(
                DeviceError(
                    code="unknown_message_type",
                    message=f"Unsupported message type: {message_type}",
                ).model_dump()
            )

    except WebSocketDisconnect:
        pass
    finally:
        if device_id is not None:
            current = connection_manager.get(device_id)

            if current is websocket:
                connection_manager.detach(device_id, websocket)

                if connection_manager.registry.exists(device_id):
                    connection_manager.registry.disconnect(device_id)
