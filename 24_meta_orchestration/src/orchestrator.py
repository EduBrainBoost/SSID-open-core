"""Orchestrator for 24_meta_orchestration.

Provides the Orchestrator interface for dispatching and tracking
tasks across SSID roots and agents.  Tasks are stored in an in-memory
ledger and progress through a deterministic lifecycle.

SoT v4.1.0 | ROOT-24-LOCK
"""
from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(str, Enum):
    """Lifecycle status of a dispatched task."""

    PENDING = "pending"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    """Internal record of a dispatched task."""

    task_id: str
    spec: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )
    updated_at: str = ""


class Orchestrator:
    """Dispatches tasks and tracks their lifecycle.

    Tasks are stored in an in-memory ledger.  An optional executor callback
    is invoked when a task is dispatched; if no executor is configured, the
    task is recorded as DISPATCHED for external processing.
    """

    def __init__(
        self, executor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    ) -> None:
        """Initialise the Orchestrator.

        Args:
            executor: Optional callable that executes a task spec and returns
                a result dict.  When None, tasks are recorded as DISPATCHED
                but not executed inline.
        """
        self._ledger: Dict[str, TaskRecord] = {}
        self._executor = executor

    def dispatch_task(self, task_spec: dict) -> dict:
        """Dispatch a task for execution.

        Args:
            task_spec: Task specification dict.

        Returns:
            dict with task_id and status.
        """
        task_id = str(uuid.uuid4())
        record = TaskRecord(task_id=task_id, spec=task_spec)

        if self._executor is not None:
            record.status = TaskStatus.RUNNING
            try:
                result = self._executor(task_spec)
                record.status = TaskStatus.COMPLETED
                record.result = result
            except Exception as exc:  # noqa: BLE001
                record.status = TaskStatus.FAILED
                record.error = str(exc)
        else:
            record.status = TaskStatus.DISPATCHED

        record.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._ledger[task_id] = record

        return {"task_id": task_id, "status": record.status.value}

    def get_task_status(self, task_id: str) -> dict:
        """Query the current status of a dispatched task.

        Args:
            task_id: Unique task identifier.

        Returns:
            dict with task_id, status, and optional result/error.

        Raises:
            KeyError: If the task_id is not found in the ledger.
        """
        record = self._ledger[task_id]
        out: Dict[str, Any] = {
            "task_id": record.task_id,
            "status": record.status.value,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        if record.result is not None:
            out["result"] = record.result
        if record.error is not None:
            out["error"] = record.error
        return out

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[dict]:
        """List tasks, optionally filtered by status.

        Args:
            status: If provided, only tasks in this status are returned.

        Returns:
            List of task summary dicts.
        """
        results = []
        for record in self._ledger.values():
            if status is not None and record.status != status:
                continue
            results.append(
                {
                    "task_id": record.task_id,
                    "status": record.status.value,
                    "created_at": record.created_at,
                }
            )
        return results

    def cancel_task(self, task_id: str) -> dict:
        """Cancel a pending or dispatched task.

        Args:
            task_id: Unique task identifier.

        Returns:
            dict with task_id and updated status.

        Raises:
            KeyError: If the task_id is not found.
            ValueError: If the task is not in a cancellable state.
        """
        record = self._ledger[task_id]
        if record.status not in (TaskStatus.PENDING, TaskStatus.DISPATCHED):
            raise ValueError(
                f"Task {task_id} is in state {record.status.value} and cannot be cancelled."
            )
        record.status = TaskStatus.CANCELLED
        record.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {"task_id": task_id, "status": record.status.value}
