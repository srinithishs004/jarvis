import pytest
from pydantic import ValidationError

from app.models.device import (
    DeviceCapabilities,
    DeviceHeartbeat,
    DeviceRegistration,
    DeviceType,
)
from app.models.device_protocol import (
    DeviceAck,
    DeviceCapabilitiesMessage,
    DeviceCommand,
    DeviceCommandResult,
    DeviceError,
    DeviceHeartbeatMessage,
    DeviceHello,
)


def registration():
    return DeviceRegistration(
        device_id="windows-01",
        device_name="JARVIS Windows",
        device_type=DeviceType.WINDOWS,
        agent_version="0.1.0",
        capabilities=DeviceCapabilities(
            capabilities=["keyboard"],
            tool_names=["windows.keyboard"],
        ),
    )


def test_hello_message():
    message = DeviceHello(registration=registration())

    assert message.type == "hello"
    assert message.registration.device_id == "windows-01"


def test_heartbeat_message():
    message = DeviceHeartbeatMessage(
        heartbeat=DeviceHeartbeat(device_id="windows-01")
    )

    assert message.type == "heartbeat"
    assert message.heartbeat.device_id == "windows-01"


def test_capabilities_message():
    message = DeviceCapabilitiesMessage(
        device_id="windows-01",
        capabilities=DeviceCapabilities(
            capabilities=["keyboard", "mouse"],
            tool_names=["windows.keyboard"],
        ),
    )

    assert message.type == "capabilities"
    assert message.capabilities.tool_names == ["windows.keyboard"]


def test_ack_message():
    message = DeviceAck(request_type="hello")

    assert message.type == "ack"
    assert message.request_type == "hello"


def test_error_message():
    message = DeviceError(
        code="invalid_message",
        message="Invalid device message",
    )

    assert message.type == "error"
    assert message.code == "invalid_message"


def test_command_message():
    message = DeviceCommand(
        request_id="req-123",
        tool_name="windows.keyboard",
        arguments={"text": "hello"},
    )

    assert message.type == "command"
    assert message.request_id == "req-123"
    assert message.arguments["text"] == "hello"


def test_command_result_success():
    message = DeviceCommandResult(
        request_id="req-123",
        success=True,
        result={"ok": True},
    )

    assert message.type == "command_result"
    assert message.success is True


def test_command_result_failure():
    message = DeviceCommandResult(
        request_id="req-123",
        success=False,
        error="Command rejected",
    )

    assert message.success is False
    assert message.error == "Command rejected"


def test_hello_requires_registration():
    with pytest.raises(ValidationError):
        DeviceHello.model_validate({
            "type": "hello",
        })


def test_command_requires_request_id():
    with pytest.raises(ValidationError):
        DeviceCommand.model_validate({
            "type": "command",
            "tool_name": "windows.keyboard",
        })
