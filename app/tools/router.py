import threading
from time import perf_counter
from typing import Any

from app.core.audit import AuditEvent, AuditLogger
from app.core.confirmation import ConfirmationManager
from app.core.executor import ProcessExecutor
from app.core.permissions import PermissionEngine
from app.core.tasks import TaskManager
from app.db.audit import AuditRepository
from app.tools.registry import ToolRegistry


class ToolRouter:
    def __init__(
        self,
        registry: ToolRegistry,
        permission_engine: PermissionEngine | None = None,
        confirmation_manager: ConfirmationManager | None = None,
        audit_logger: AuditLogger | None = None,
        audit_repository: AuditRepository | None = None,
        task_manager: TaskManager | None = None,
        executor: ProcessExecutor | None = None,
    ) -> None:
        self.registry = registry
        self.permission_engine = permission_engine or PermissionEngine()
        self.confirmation_manager = (
            confirmation_manager or ConfirmationManager()
        )
        self.audit_logger = audit_logger or AuditLogger()
        self.audit_repository = audit_repository or AuditRepository()
        self.task_manager = task_manager or TaskManager()
        self.executor = executor or ProcessExecutor()

    def _audit(
        self,
        *,
        event_type: str,
        tool_name: str,
        success: bool,
        started_at: float,
        permission_level: str | None = None,
        confirmation_id: str | None = None,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        error_type: str | None = None,
    ) -> None:
        event = AuditEvent(
            event_type=event_type,
            tool_name=tool_name,
            success=success,
            permission_level=permission_level,
            confirmation_id=confirmation_id,
            arguments=arguments or {},
            result=result,
            error_type=error_type,
            duration_ms=(perf_counter() - started_at) * 1000,
        )

        self.audit_logger.record(event)
        self.audit_repository.record(event)

    def execute_background(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Start a tool without holding the HTTP request open.

        Permission/confirmation checks happen synchronously.
        Actual execution happens in a background thread, with the
        existing ProcessExecutor providing process isolation.
        """
        started_at = perf_counter()
        arguments = arguments or {}

        try:
            tool = self.registry.get(name)
        except KeyError as exc:
            self._audit(
                event_type="tool_not_found",
                tool_name=name,
                success=False,
                started_at=started_at,
                arguments=arguments,
                error_type="tool_not_found",
            )
            return {
                "ok": False,
                "tool": name,
                "error": str(exc),
                "error_type": "tool_not_found",
            }

        decision = self.permission_engine.evaluate(tool)

        if not decision.allowed:
            if not confirmation_id or not self.confirmation_manager.is_approved(
                confirmation_id,
                name,
            ):
                request = self.confirmation_manager.create(name)

                self._audit(
                    event_type="confirmation_required",
                    tool_name=name,
                    success=False,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=request.confirmation_id,
                    arguments=arguments,
                    error_type="confirmation_required",
                )

                return {
                    "ok": False,
                    "tool": name,
                    "error": decision.reason,
                    "error_type": "confirmation_required",
                    "requires_confirmation": True,
                    "confirmation_id": request.confirmation_id,
                    "expires_at": request.expires_at.isoformat(),
                }

        if tool.handler is None:
            self._audit(
                event_type="missing_handler",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="missing_handler",
            )
            return {
                "ok": False,
                "tool": name,
                "error": f"Tool has no handler: {name}",
                "error_type": "missing_handler",
            }

        task = self.task_manager.create(
            tool_name=name,
            arguments=arguments,
            confirmation_id=confirmation_id,
        )
        self.task_manager.mark_running(task.task_id)

        thread = threading.Thread(
            target=self._execute_task,
            args=(
                task.task_id,
                tool,
                arguments,
                confirmation_id,
                started_at,
            ),
            daemon=True,
            name=f"jarvis-task-{task.task_id[:8]}",
        )
        thread.start()

        return {
            "ok": True,
            "tool": name,
            "task_id": task.task_id,
            "status": "running",
        }

    def _execute_task(
        self,
        task_id: str,
        tool,
        arguments: dict[str, Any],
        confirmation_id: str | None,
        started_at: float,
    ) -> None:
        try:
            status, value = self.executor.run(
                handler=tool.handler,
                arguments=arguments,
                timeout_seconds=tool.timeout_seconds,
                cancel_check=lambda: self.task_manager.is_cancel_requested(
                    task_id
                ),
                heartbeat=lambda: self.task_manager.heartbeat(
                    task_id
                ),
            )

            if status == "succeeded":
                self.task_manager.mark_succeeded(
                    task_id,
                    result=value,
                )
                self._audit(
                    event_type="tool_execution",
                    tool_name=tool.name,
                    success=True,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=confirmation_id,
                    arguments=arguments,
                    result=value,
                )
                return

            if status == "cancelled":
                self.task_manager.mark_cancelled(task_id)
                self._audit(
                    event_type="tool_cancelled",
                    tool_name=tool.name,
                    success=False,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=confirmation_id,
                    arguments=arguments,
                    error_type="cancelled",
                )
                return

            if status == "timeout":
                error = (
                    f"Tool timed out after "
                    f"{tool.timeout_seconds} seconds"
                )
                self.task_manager.mark_failed(
                    task_id,
                    error=error,
                    error_type="timeout",
                )
                self._audit(
                    event_type="tool_timeout",
                    tool_name=tool.name,
                    success=False,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=confirmation_id,
                    arguments=arguments,
                    error_type="timeout",
                )
                return

            self.task_manager.mark_failed(
                task_id,
                error=str(value),
                error_type=status,
            )
            self._audit(
                event_type="tool_execution",
                tool_name=tool.name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type=status,
            )

        except Exception as exc:
            self.task_manager.mark_failed(
                task_id,
                error=str(exc),
                error_type="execution_error",
            )
            self._audit(
                event_type="tool_execution",
                tool_name=tool.name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="execution_error",
            )

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        arguments = arguments or {}

        try:
            tool = self.registry.get(name)
        except KeyError as exc:
            self._audit(
                event_type="tool_not_found",
                tool_name=name,
                success=False,
                started_at=started_at,
                arguments=arguments,
                error_type="tool_not_found",
            )

            return {
                "ok": False,
                "tool": name,
                "error": str(exc),
                "error_type": "tool_not_found",
            }

        decision = self.permission_engine.evaluate(tool)

        if not decision.allowed:
            if not confirmation_id or not self.confirmation_manager.is_approved(
                confirmation_id,
                name,
            ):
                request = self.confirmation_manager.create(name)

                self._audit(
                    event_type="confirmation_required",
                    tool_name=name,
                    success=False,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=request.confirmation_id,
                    arguments=arguments,
                    error_type="confirmation_required",
                )

                return {
                    "ok": False,
                    "tool": name,
                    "error": decision.reason,
                    "error_type": "confirmation_required",
                    "requires_confirmation": True,
                    "confirmation_id": request.confirmation_id,
                    "expires_at": request.expires_at.isoformat(),
                }

        if tool.handler is None:
            self._audit(
                event_type="missing_handler",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="missing_handler",
            )

            return {
                "ok": False,
                "tool": name,
                "error": f"Tool has no handler: {name}",
                "error_type": "missing_handler",
            }

        task = self.task_manager.create(
            tool_name=name,
            arguments=arguments,
            confirmation_id=confirmation_id,
        )

        self.task_manager.mark_running(task.task_id)

        try:
            status, value = self.executor.run(
                handler=tool.handler,
                arguments=arguments,
                timeout_seconds=tool.timeout_seconds,
                cancel_check=lambda: self.task_manager.is_cancel_requested(
                    task.task_id
                ),
                heartbeat=lambda: self.task_manager.heartbeat(
                    task.task_id
                ),
            )

            if status == "succeeded":
                self.task_manager.mark_succeeded(
                    task.task_id,
                    result=value,
                )

                self._audit(
                    event_type="tool_execution",
                    tool_name=name,
                    success=True,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=confirmation_id,
                    arguments=arguments,
                    result=value,
                )

                return {
                    "ok": True,
                    "tool": name,
                    "result": value,
                    "task_id": task.task_id,
                }

            if status == "cancelled":
                self.task_manager.mark_cancelled(task.task_id)

                self._audit(
                    event_type="tool_cancelled",
                    tool_name=name,
                    success=False,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=confirmation_id,
                    arguments=arguments,
                    error_type="cancelled",
                )

                return {
                    "ok": False,
                    "tool": name,
                    "error": "Tool execution cancelled",
                    "error_type": "cancelled",
                    "task_id": task.task_id,
                }

            if status == "timeout":
                error = (
                    f"Tool timed out after "
                    f"{tool.timeout_seconds} seconds"
                )

                self.task_manager.mark_failed(
                    task.task_id,
                    error=error,
                    error_type="timeout",
                )

                self._audit(
                    event_type="tool_timeout",
                    tool_name=name,
                    success=False,
                    started_at=started_at,
                    permission_level=tool.permission.name,
                    confirmation_id=confirmation_id,
                    arguments=arguments,
                    error_type="timeout",
                )

                return {
                    "ok": False,
                    "tool": name,
                    "error": error,
                    "error_type": "timeout",
                    "task_id": task.task_id,
                }

            self.task_manager.mark_failed(
                task.task_id,
                error=str(value),
                error_type=status,
            )

            self._audit(
                event_type="tool_execution",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type=status,
            )

            return {
                "ok": False,
                "tool": name,
                "error": str(value),
                "error_type": status,
                "task_id": task.task_id,
            }

        except Exception as exc:
            self.task_manager.mark_failed(
                task.task_id,
                error=str(exc),
                error_type="execution_error",
            )

            self._audit(
                event_type="tool_execution",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="execution_error",
            )

            return {
                "ok": False,
                "tool": name,
                "error": str(exc),
                "error_type": "execution_error",
                "task_id": task.task_id,
            }
