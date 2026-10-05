import os
from time import perf_counter
from typing import Any

from app.core.audit import AuditEvent, AuditLogger
from app.core.confirmation import ConfirmationManager
from app.core.executor import ProcessExecutor
from app.core.remote_executor import RemoteToolExecutor
from app.core.permissions import PermissionEngine
from app.core.tasks import TaskManager
from app.db.audit import AuditRepository
from app.tools.registry import ToolRegistry
from app.core.worker_pool import TaskWorkerPool, WorkItem
from app.models.capability import ExecutionLocation
from app.core.tool_arguments import (
    ToolArgumentError,
    validate_tool_arguments,
)


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
        remote_executor: RemoteToolExecutor | None = None,
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
        self.remote_executor = remote_executor
        self.worker_pool = TaskWorkerPool(
            self._run_background_item,
            max_workers=int(os.getenv("JARVIS_MAX_WORKERS", "2")),
            max_queue_size=int(os.getenv("JARVIS_MAX_QUEUE", "16")),
        )

    def _run_background_item(self, item: WorkItem) -> None:
        task = self.task_manager.get(item.task_id)

        if self.task_manager.is_kill_switch_active():
            self.task_manager.request_cancel(item.task_id)
            return

        # The task may have been cancelled while waiting in the queue.
        if task.cancel_requested or task.status.value != "queued":
            return

        tool = self.registry.get(item.tool_name)

        self.task_manager.mark_running(item.task_id)

        self._execute_task(
            item.task_id,
            tool,
            item.args,
            item.confirmation_id,
            perf_counter(),
        )

    def recover_queued_tasks(self) -> int:
        recovered = 0

        for task in self.task_manager.queued_tasks():
            if task.cancel_requested:
                continue

            accepted = self.worker_pool.submit(
                WorkItem(
                    task_id=task.task_id,
                    tool_name=task.tool_name,
                    args=task.arguments,
                    confirmation_id=task.confirmation_id,
                )
            )

            if accepted:
                recovered += 1

        return recovered

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

        if self.task_manager.is_kill_switch_active():
            return {
                "ok": False,
                "tool": name,
                "error": "JARVIS kill switch is active",
                "error_type": "kill_switch_active",
            }

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

        try:
            validate_tool_arguments(
                arguments,
                tool.input_schema,
            )
        except ToolArgumentError as exc:
            self._audit(
                event_type="invalid_tool_arguments",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="invalid_tool_arguments",
            )
            return {
                "ok": False,
                "tool": name,
                "error": str(exc),
                "error_type": "invalid_tool_arguments",
            }

        if tool.execution_location == ExecutionLocation.LOCAL and tool.handler is None:
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

        if (
            tool.execution_location == ExecutionLocation.REMOTE
            and self.remote_executor is None
        ):
            self._audit(
                event_type="missing_remote_executor",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="missing_remote_executor",
            )
            return {
                "ok": False,
                "tool": name,
                "error": f"Tool has no remote executor: {name}",
                "error_type": "missing_remote_executor",
            }

        task = self.task_manager.create(
            tool_name=name,
            arguments=arguments,
            confirmation_id=confirmation_id,
        )

        if self.task_manager.is_kill_switch_active():
            self.task_manager.request_cancel(task.task_id)
            return {
                "ok": False,
                "tool": name,
                "task_id": task.task_id,
                "status": "cancelled",
                "error": "JARVIS kill switch is active",
                "error_type": "kill_switch_active",
            }

        accepted = self.worker_pool.submit(
            WorkItem(
                task_id=task.task_id,
                tool_name=name,
                args=arguments,
                confirmation_id=confirmation_id,
            )
        )

        if not accepted:
            self.task_manager.request_cancel(task.task_id)

            return {
                "ok": False,
                "tool": name,
                "task_id": task.task_id,
                "status": "cancelled",
                "error": "Task queue is full",
                "error_type": "queue_full",
            }

        return {
            "ok": True,
            "tool": name,
            "task_id": task.task_id,
            "status": "queued",
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
            if tool.execution_location == ExecutionLocation.REMOTE:
                status, value = self.remote_executor.run(
                    tool_name=tool.name,
                    arguments=arguments,
                    timeout_seconds=tool.timeout_seconds,
                    cancel_check=lambda: self.task_manager.is_cancel_requested(
                        task_id
                    ),
                    heartbeat=lambda: self.task_manager.heartbeat(
                        task_id
                    ),
                )
            else:
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

        if self.task_manager.is_kill_switch_active():
            return {
                "ok": False,
                "tool": name,
                "error": "JARVIS kill switch is active",
                "error_type": "kill_switch_active",
            }

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

        try:
            validate_tool_arguments(
                arguments,
                tool.input_schema,
            )
        except ToolArgumentError as exc:
            self._audit(
                event_type="invalid_tool_arguments",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="invalid_tool_arguments",
            )
            return {
                "ok": False,
                "tool": name,
                "error": str(exc),
                "error_type": "invalid_tool_arguments",
            }

        if tool.execution_location == ExecutionLocation.LOCAL and tool.handler is None:
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

        if (
            tool.execution_location == ExecutionLocation.REMOTE
            and self.remote_executor is None
        ):
            self._audit(
                event_type="missing_remote_executor",
                tool_name=name,
                success=False,
                started_at=started_at,
                permission_level=tool.permission.name,
                confirmation_id=confirmation_id,
                arguments=arguments,
                error_type="missing_remote_executor",
            )

            return {
                "ok": False,
                "tool": name,
                "error": f"Tool has no remote executor: {name}",
                "error_type": "missing_remote_executor",
            }

        task = self.task_manager.create(
            tool_name=name,
            arguments=arguments,
            confirmation_id=confirmation_id,
        )

        self.task_manager.mark_running(task.task_id)

        try:
            if tool.execution_location == ExecutionLocation.REMOTE:
                status, value = self.remote_executor.run(
                    tool_name=tool.name,
                    arguments=arguments,
                    timeout_seconds=tool.timeout_seconds,
                    cancel_check=lambda: self.task_manager.is_cancel_requested(
                        task.task_id
                    ),
                    heartbeat=lambda: self.task_manager.heartbeat(
                        task.task_id
                    ),
                )
            else:
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
