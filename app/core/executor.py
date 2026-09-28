import multiprocessing
from typing import Any, Callable


def _worker_entry(
    handler: Callable[..., Any],
    arguments: dict[str, Any],
    child_conn,
) -> None:
    try:
        result = handler(**arguments)

        child_conn.send(
            {
                "ok": True,
                "result": result,
            }
        )

    except Exception as exc:
        child_conn.send(
            {
                "ok": False,
                "error": str(exc),
                "error_type": "execution_error",
            }
        )

    finally:
        child_conn.close()


class ProcessExecutor:
    def __init__(
        self,
        start_method: str = "spawn",
    ) -> None:
        self.context = multiprocessing.get_context(start_method)

    def _terminate(self, process: multiprocessing.Process) -> None:
        if not process.is_alive():
            process.join(timeout=0.2)
            return

        process.terminate()
        process.join(timeout=0.25)

        if process.is_alive():
            process.kill()
            process.join(timeout=0.5)

    def run(
        self,
        handler: Callable[..., Any],
        arguments: dict[str, Any],
        timeout_seconds: float,
        cancel_check: Callable[[], bool] | None = None,
        poll_interval: float = 0.1,
    ) -> tuple[str, Any]:
        parent_conn, child_conn = self.context.Pipe(duplex=False)

        process = self.context.Process(
            target=_worker_entry,
            args=(handler, arguments, child_conn),
        )

        process.start()
        child_conn.close()

        elapsed = 0.0

        try:
            while process.is_alive():
                if cancel_check and cancel_check():
                    self._terminate(process)
                    return "cancelled", None

                process.join(timeout=poll_interval)
                elapsed += poll_interval

                if elapsed >= timeout_seconds:
                    self._terminate(process)
                    return "timeout", None

            if parent_conn.poll():
                try:
                    payload = parent_conn.recv()
                except EOFError:
                    return "execution_error", "Worker exited without a result"

                if payload["ok"]:
                    return "succeeded", payload["result"]

                return (
                    payload.get("error_type", "execution_error"),
                    payload.get("error", "Unknown execution error"),
                )

            return "execution_error", "Worker exited without a result"

        finally:
            parent_conn.close()

            if process.is_alive():
                self._terminate(process)
