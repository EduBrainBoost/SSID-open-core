"""
SSID EMS Orchestrator — Central Operating System
Root: 24_meta_orchestration | Shard: 01_identitaet_personen

Central task intake, orchestration, run tracking, evidence collection.
EMS-first: all SSID operations are EMS-initiated and EMS-verified.
"""
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class RunStatus(Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


@dataclass
class EMSTask:
    task_id: str
    title: str
    scope: str
    root_id: str
    shard_id: str
    status: TaskStatus
    created_at: str
    assigned_agent: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    evidence_hash: Optional[str] = None
    result: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "scope": self.scope,
            "root_id": self.root_id,
            "shard_id": self.shard_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "assigned_agent": self.assigned_agent,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "evidence_hash": self.evidence_hash,
        }


@dataclass
class RunRecord:
    run_id: str
    task_id: str
    agent_id: str
    status: RunStatus
    started_at: str
    completed_at: Optional[str] = None
    output_hash: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "output_hash": self.output_hash,
            "duration_ms": self.duration_ms,
        }


class EMSOrchestrator:
    """Central EMS orchestration engine."""

    def __init__(self):
        self._tasks: dict[str, EMSTask] = {}
        self._runs: dict[str, RunRecord] = {}
        self._run_ledger: list[dict] = []

    def create_task(
        self, title: str, scope: str, root_id: str, shard_id: str
    ) -> EMSTask:
        task_id = f"ems-task-{uuid.uuid4().hex[:12]}"
        task = EMSTask(
            task_id=task_id,
            title=title,
            scope=scope,
            root_id=root_id,
            shard_id=shard_id,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._tasks[task_id] = task
        return task

    def assign_task(self, task_id: str, agent_id: str) -> EMSTask:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.assigned_agent = agent_id
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc).isoformat()
        return task

    def start_run(self, task_id: str, agent_id: str) -> RunRecord:
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        run = RunRecord(
            run_id=run_id,
            task_id=task_id,
            agent_id=agent_id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._runs[run_id] = run
        return run

    def complete_run(self, run_id: str, output: dict, success: bool = True) -> RunRecord:
        run = self._runs.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        now = datetime.now(timezone.utc).isoformat()
        run.status = RunStatus.SUCCESS if success else RunStatus.FAILURE
        run.completed_at = now
        run.output_hash = hashlib.sha256(
            json.dumps(output, sort_keys=True).encode()
        ).hexdigest()

        self._run_ledger.append(run.to_dict())

        # Update task
        task = self._tasks.get(run.task_id)
        if task:
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            task.completed_at = now
            task.evidence_hash = run.output_hash

        return run

    def emergency_stop(self, task_id: str, reason: str) -> dict:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.CANCELLED
        return {
            "task_id": task_id,
            "action": "emergency_stop",
            "reason": reason,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def get_task(self, task_id: str) -> Optional[EMSTask]:
        return self._tasks.get(task_id)

    def get_active_tasks(self) -> list[EMSTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS]

    def get_run_ledger(self) -> list[dict]:
        return list(self._run_ledger)

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def run_count(self) -> int:
        return len(self._runs)
