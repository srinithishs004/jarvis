import threading
import time

import pytest

from app.devices.commands import DeviceCommandService
from app.models.device_protocol import DeviceCommandResult


class FakeConnectionManager:
    def __init__(self):
        self.sent = []

    async def send(self, device_id, message):
        self.sent.append((device_id, message))
        return True


def test_command_service_correlates_result():
    connection = FakeConnectionManager()
    service = DeviceCommandService(connection)

    result_holder = {}

    def run():
        result_holder["result"] = service.execute(
            "windows-01",
            "windows.keyboard",
            {"text": "hello"},
            timeout_seconds=2,
        )

    worker = threading.Thread(target=run)
    worker.start()

    deadline = time.time() + 2
    while not connection.sent and time.time() < deadline:
        time.sleep(0.01)

    assert connection.sent
    device_id, message = connection.sent[0]

    assert device_id == "windows-01"
    assert message["type"] == "command"
    assert message["tool_name"] == "windows.keyboard"
    assert message["arguments"] == {"text": "hello"}

    service.handle_result(
        DeviceCommandResult(
            request_id=message["request_id"],
            success=True,
            result={"typed": True},
        )
    )

    worker.join(timeout=2)

    assert not worker.is_alive()
    assert result_holder["result"] == {
        "ok": True,
        "result": {"typed": True},
    }


def test_command_service_propagates_device_failure():
    connection = FakeConnectionManager()
    service = DeviceCommandService(connection)

    result_holder = {}

    def run():
        result_holder["result"] = service.execute(
            "windows-01",
            "windows.keyboard",
            {"text": "hello"},
            timeout_seconds=2,
        )

    worker = threading.Thread(target=run)
    worker.start()

    deadline = time.time() + 2
    while not connection.sent and time.time() < deadline:
        time.sleep(0.01)

    message = connection.sent[0][1]

    service.handle_result(
        DeviceCommandResult(
            request_id=message["request_id"],
            success=False,
            error="Keyboard unavailable",
        )
    )

    worker.join(timeout=2)

    assert not worker.is_alive()
    assert result_holder["result"] == {
        "ok": False,
        "error": "Keyboard unavailable",
    }


def test_command_service_ignores_unknown_result():
    connection = FakeConnectionManager()
    service = DeviceCommandService(connection)

    assert service.handle_result(
        DeviceCommandResult(
            request_id="unknown-request",
            success=True,
            result={"ok": True},
        )
    ) is False


def test_command_service_timeout_cleans_pending_request():
    connection = FakeConnectionManager()
    service = DeviceCommandService(connection)

    result = service.execute(
        "windows-01",
        "windows.keyboard",
        {"text": "hello"},
        timeout_seconds=0.05,
    )

    assert result["ok"] is False
    assert result["error_type"] == "timeout"
    assert service.pending_count() == 0


def test_command_service_rejects_disconnected_device():
    class DisconnectedConnection:
        async def send(self, device_id, message):
            return False

    service = DeviceCommandService(DisconnectedConnection())

    result = service.execute(
        "windows-offline",
        "windows.keyboard",
        {"text": "hello"},
        timeout_seconds=1,
    )

    assert result == {
        "ok": False,
        "error": "Device not connected: windows-offline",
        "error_type": "device_not_connected",
    }
    assert service.pending_count() == 0


def test_late_result_after_timeout_is_ignored():
    connection = FakeConnectionManager()
    service = DeviceCommandService(connection)

    result = service.execute(
        "windows-01",
        "windows.keyboard",
        {"text": "hello"},
        timeout_seconds=0.05,
    )

    assert result["error_type"] == "timeout"
    assert service.pending_count() == 0

    assert service.handle_result(
        DeviceCommandResult(
            request_id="expired-request",
            success=True,
            result={"typed": True},
        )
    ) is False


def test_command_service_correlates_concurrent_results():
    connection = FakeConnectionManager()
    service = DeviceCommandService(connection)

    results = {}

    def run(name, text):
        results[name] = service.execute(
            "windows-01",
            "windows.keyboard",
            {"text": text},
            timeout_seconds=2,
        )

    first = threading.Thread(target=run, args=("first", "one"))
    second = threading.Thread(target=run, args=("second", "two"))

    first.start()
    second.start()

    deadline = time.time() + 2
    while len(connection.sent) < 2 and time.time() < deadline:
        time.sleep(0.01)

    assert len(connection.sent) == 2

    messages = [item[1] for item in connection.sent]
    request_by_text = {
        message["arguments"]["text"]: message["request_id"]
        for message in messages
    }

    service.handle_result(
        DeviceCommandResult(
            request_id=request_by_text["two"],
            success=True,
            result={"text": "TWO"},
        )
    )
    service.handle_result(
        DeviceCommandResult(
            request_id=request_by_text["one"],
            success=True,
            result={"text": "ONE"},
        )
    )

    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert results["first"] == {
        "ok": True,
        "result": {"text": "ONE"},
    }
    assert results["second"] == {
        "ok": True,
        "result": {"text": "TWO"},
    }
    assert service.pending_count() == 0
