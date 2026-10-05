from app.core.remote_executor import RemoteToolExecutor


class FakeCommandService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(
        self,
        device_id,
        tool_name,
        arguments,
        *,
        timeout_seconds,
        cancel_check=None,
        heartbeat=None,
    ):
        self.calls.append(
            {
                "device_id": device_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "timeout_seconds": timeout_seconds,
                "cancel_check": cancel_check,
                "heartbeat": heartbeat,
            }
        )
        return self.result


def test_remote_executor_returns_success():
    service = FakeCommandService(
        {
            "ok": True,
            "result": {"hostname": "WIN-01"},
        }
    )
    executor = RemoteToolExecutor(service)

    status, value = executor.run(
        tool_name="windows.system.info",
        arguments={"device_id": "windows-01"},
        timeout_seconds=10,
    )

    assert status == "succeeded"
    assert value == {"hostname": "WIN-01"}

    assert service.calls == [
        {
            "device_id": "windows-01",
            "tool_name": "windows.system.info",
            "arguments": {},
            "timeout_seconds": 10,
            "cancel_check": None,
            "heartbeat": None,
        }
    ]


def test_remote_executor_maps_timeout():
    service = FakeCommandService(
        {
            "ok": False,
            "error": "Device command timed out",
            "error_type": "timeout",
        }
    )
    executor = RemoteToolExecutor(service)

    status, value = executor.run(
        tool_name="windows.system.info",
        arguments={"device_id": "windows-01"},
        timeout_seconds=3,
    )

    assert status == "timeout"
    assert value is None


def test_remote_executor_maps_cancellation():
    service = FakeCommandService(
        {
            "ok": False,
            "error": "Device command cancelled",
            "error_type": "cancelled",
        }
    )
    executor = RemoteToolExecutor(service)

    cancel_check = lambda: True

    status, value = executor.run(
        tool_name="windows.system.info",
        arguments={"device_id": "windows-01"},
        timeout_seconds=3,
        cancel_check=cancel_check,
    )

    assert status == "cancelled"
    assert value is None
    assert service.calls[0]["cancel_check"] is cancel_check


def test_remote_executor_maps_device_failure():
    service = FakeCommandService(
        {
            "ok": False,
            "error": "Keyboard unavailable",
        }
    )
    executor = RemoteToolExecutor(service)

    status, value = executor.run(
        tool_name="windows.keyboard",
        arguments={
            "device_id": "windows-01",
            "text": "hello",
        },
        timeout_seconds=10,
    )

    assert status == "execution_error"
    assert value == "Keyboard unavailable"
