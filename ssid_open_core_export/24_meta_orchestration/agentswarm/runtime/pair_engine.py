"""
AgentSwarm Pair Runtime Engine.
Manages primary+sentinel pairs with heartbeat, takeover, state handoff, and evidence.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PairState(Enum):
    IDLE = "idle"
    PRIMARY_RUNNING = "primary_running"
    SENTINEL_MONITORING = "sentinel_monitoring"
    TAKEOVER_TRIGGERED = "takeover_triggered"
    SENTINEL_ACTIVE = "sentinel_active"
    COMPLETED = "completed"
    FAILED = "failed"


class TakeoverReason(Enum):
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"
    STAGNATION = "stagnation"
    REPEATED_ERROR = "repeated_error"
    MAX_RUNTIME = "max_runtime_exceeded"
    POLICY_VIOLATION = "policy_violation"
    MANUAL = "manual_takeover"


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Heartbeat:
    agent_id: str
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0
    progress_pct: float = 0.0
    last_evidence_hash: str = ""


@dataclass
class WorkerResult:
    agent_id: str
    status: str  # pass, fail, partial, blocked
    output: dict[str, Any] = field(default_factory=dict)
    evidence_hash: str = ""
    duration_ms: float = 0.0
    error: str = ""


@dataclass
class PairRun:
    pair_id: str
    run_id: str = field(default_factory=lambda: f"pair-run-{uuid.uuid4().hex[:12]}")
    state: PairState = PairState.IDLE
    primary_agent_id: str = ""
    sentinel_agent_id: str = ""
    heartbeats: list[Heartbeat] = field(default_factory=list)
    takeover_reason: TakeoverReason | None = None
    primary_result: WorkerResult | None = None
    sentinel_result: WorkerResult | None = None
    checkpoint: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""

    def _event(self, event_type: str, detail: str = ""):
        self.events.append({"ts": _utc_now(), "event": event_type, "detail": detail})

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "run_id": self.run_id,
            "state": self.state.value,
            "primary_agent_id": self.primary_agent_id,
            "sentinel_agent_id": self.sentinel_agent_id,
            "heartbeat_count": len(self.heartbeats),
            "takeover_reason": self.takeover_reason.value if self.takeover_reason else None,
            "primary_result": self.primary_result.__dict__ if self.primary_result else None,
            "sentinel_result": self.sentinel_result.__dict__ if self.sentinel_result else None,
            "checkpoint": self.checkpoint,
            "events": self.events,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


class PairEngine:
    """Runs an agent pair: primary executes, sentinel monitors, takeover on failure."""

    def __init__(
        self,
        pair_id: str,
        primary_agent_id: str,
        sentinel_agent_id: str,
        heartbeat_interval_ms: int = 30000,
        heartbeat_max_missed: int = 3,
        max_runtime_seconds: int = 300,
        evidence_dir: Path | None = None,
    ):
        self.pair_id = pair_id
        self.primary_id = primary_agent_id
        self.sentinel_id = sentinel_agent_id
        self.hb_interval = heartbeat_interval_ms / 1000.0
        self.hb_max_missed = heartbeat_max_missed
        self.max_runtime = max_runtime_seconds
        self.evidence_dir = evidence_dir

    def execute(
        self,
        primary_fn: Callable[[PairRun], WorkerResult],
        sentinel_fn: Callable[[PairRun], WorkerResult],
        task_input: dict | None = None,
    ) -> PairRun:
        """Execute the pair: primary runs, sentinel monitors and can takeover."""
        run = PairRun(
            pair_id=self.pair_id,
            primary_agent_id=self.primary_id,
            sentinel_agent_id=self.sentinel_id,
            started_at=_utc_now(),
        )
        run.checkpoint = {"task_input": task_input or {}, "step": 0}
        run._event("PAIR_START", f"primary={self.primary_id} sentinel={self.sentinel_id}")

        # Phase 1: Primary executes
        run.state = PairState.PRIMARY_RUNNING
        run._event("PRIMARY_START", self.primary_id)

        start = time.time()
        try:
            result = primary_fn(run)
            run.primary_result = result
            elapsed = (time.time() - start) * 1000
            run.primary_result.duration_ms = elapsed

            # Emit heartbeat
            hb = Heartbeat(
                agent_id=self.primary_id,
                sequence=len(run.heartbeats) + 1,
                progress_pct=100.0 if result.status == "pass" else 50.0,
                last_evidence_hash=result.evidence_hash,
            )
            run.heartbeats.append(hb)
            run._event("HEARTBEAT", f"seq={hb.sequence} progress={hb.progress_pct}%")

            if result.status == "pass":
                run._event("PRIMARY_PASS", f"evidence={result.evidence_hash[:16]}")
                run.state = PairState.COMPLETED
                run.ended_at = _utc_now()
                self._write_evidence(run)
                return run

            # Primary failed — trigger takeover
            run._event("PRIMARY_FAIL", f"error={result.error}")

        except Exception as exc:
            run.primary_result = WorkerResult(
                agent_id=self.primary_id,
                status="fail",
                error=str(exc),
                duration_ms=(time.time() - start) * 1000,
            )
            run._event("PRIMARY_EXCEPTION", str(exc))

        # Check runtime exceeded
        if (time.time() - start) > self.max_runtime:
            run.takeover_reason = TakeoverReason.MAX_RUNTIME
        elif run.primary_result and run.primary_result.status == "fail":
            run.takeover_reason = TakeoverReason.REPEATED_ERROR
        else:
            run.takeover_reason = TakeoverReason.HEARTBEAT_TIMEOUT

        # Phase 2: Sentinel takeover
        run.state = PairState.TAKEOVER_TRIGGERED
        run._event("TAKEOVER_TRIGGERED", f"reason={run.takeover_reason.value}")

        run.state = PairState.SENTINEL_ACTIVE
        run._event("SENTINEL_START", self.sentinel_id)

        try:
            sentinel_result = sentinel_fn(run)
            run.sentinel_result = sentinel_result
            run._event("SENTINEL_DONE", f"status={sentinel_result.status}")

            if sentinel_result.status == "pass":
                run.state = PairState.COMPLETED
            else:
                run.state = PairState.FAILED
        except Exception as exc:
            run.sentinel_result = WorkerResult(agent_id=self.sentinel_id, status="fail", error=str(exc))
            run.state = PairState.FAILED
            run._event("SENTINEL_EXCEPTION", str(exc))

        run.ended_at = _utc_now()
        self._write_evidence(run)
        return run

    def simulate_heartbeat_failure(
        self,
        sentinel_fn: Callable[[PairRun], WorkerResult],
    ) -> PairRun:
        """Simulate a heartbeat failure and sentinel takeover."""
        run = PairRun(
            pair_id=self.pair_id,
            primary_agent_id=self.primary_id,
            sentinel_agent_id=self.sentinel_id,
            started_at=_utc_now(),
        )
        run._event("PAIR_START", "heartbeat_failure_simulation")
        run.state = PairState.PRIMARY_RUNNING
        run._event("PRIMARY_START", self.primary_id)

        # Simulate: no heartbeats received
        run._event("HEARTBEAT_MISSED", f"missed={self.hb_max_missed}")
        run.takeover_reason = TakeoverReason.HEARTBEAT_TIMEOUT
        run.state = PairState.TAKEOVER_TRIGGERED
        run._event("TAKEOVER_TRIGGERED", "heartbeat_timeout")

        # Sentinel takes over
        run.state = PairState.SENTINEL_ACTIVE
        run._event("SENTINEL_START", self.sentinel_id)

        try:
            result = sentinel_fn(run)
            run.sentinel_result = result
            run.state = PairState.COMPLETED if result.status == "pass" else PairState.FAILED
            run._event("SENTINEL_DONE", f"status={result.status}")
        except Exception as exc:
            run.sentinel_result = WorkerResult(agent_id=self.sentinel_id, status="fail", error=str(exc))
            run.state = PairState.FAILED
            run._event("SENTINEL_EXCEPTION", str(exc))

        run.ended_at = _utc_now()
        self._write_evidence(run)
        return run

    def _write_evidence(self, run: PairRun) -> None:
        if not self.evidence_dir:
            return
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        data = json.dumps(run.to_dict(), indent=2, ensure_ascii=False)
        evidence_hash = _sha256(data)
        manifest = {
            "run_id": run.run_id,
            "pair_id": run.pair_id,
            "state": run.state.value,
            "evidence_hash": evidence_hash,
            "sealed_at": _utc_now(),
        }
        (self.evidence_dir / f"{run.run_id}.json").write_text(data, encoding="utf-8")
        (self.evidence_dir / f"{run.run_id}.seal.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
