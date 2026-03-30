"""
SSIDCTL v2 Runtime State Machine — deterministic state transitions.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RunState(Enum):
    REGISTERED = "REGISTERED"
    PROFILE_SELECTED = "PROFILE_SELECTED"
    PRECHECK = "PRECHECK"
    LOCK_ACQUIRED = "LOCK_ACQUIRED"
    PLANNED = "PLANNED"
    AGENTS_RESOLVED = "AGENTS_RESOLVED"
    SANDBOX_READY = "SANDBOX_READY"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    EVIDENCE_SEALING = "EVIDENCE_SEALING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ABORTED = "ABORTED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"


# Explicit valid transitions — no implicit moves
VALID_TRANSITIONS = {
    RunState.REGISTERED: {RunState.PROFILE_SELECTED},
    RunState.PROFILE_SELECTED: {RunState.PRECHECK},
    RunState.PRECHECK: {RunState.LOCK_ACQUIRED, RunState.BLOCKED},
    RunState.LOCK_ACQUIRED: {RunState.PLANNED, RunState.BLOCKED},
    RunState.PLANNED: {RunState.AGENTS_RESOLVED, RunState.BLOCKED},
    RunState.AGENTS_RESOLVED: {RunState.SANDBOX_READY, RunState.BLOCKED},
    RunState.SANDBOX_READY: {RunState.RUNNING, RunState.BLOCKED},
    RunState.RUNNING: {RunState.VALIDATING, RunState.FAILED, RunState.ABORTED},
    RunState.VALIDATING: {
        RunState.EVIDENCE_SEALING,
        RunState.ROLLBACK_REQUIRED,
        RunState.FAILED,
    },
    RunState.EVIDENCE_SEALING: {RunState.COMPLETED, RunState.FAILED},
    # Terminal states
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.BLOCKED: set(),
    RunState.ABORTED: set(),
    RunState.ROLLBACK_REQUIRED: {RunState.FAILED},
}


def _utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass
class StateTransition:
    from_state: str
    to_state: str
    timestamp_utc: str
    reason: str = ""


@dataclass
class RunContext:
    run_id: str
    profile_id: str
    state: RunState = RunState.REGISTERED
    transitions: List[StateTransition] = field(default_factory=list)
    started_at: str = field(default_factory=_utc_now)
    ended_at: Optional[str] = None
    exit_code: int = -1
    dry_run: bool = False

    def transition(self, target: RunState, reason: str = "") -> bool:
        """Attempt a state transition. Returns True on success, False on invalid."""
        valid = VALID_TRANSITIONS.get(self.state, set())
        if target not in valid:
            return False
        ts = _utc_now()
        self.transitions.append(
            StateTransition(
                from_state=self.state.value,
                to_state=target.value,
                timestamp_utc=ts,
                reason=reason,
            )
        )
        self.state = target
        if target in (
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.BLOCKED,
            RunState.ABORTED,
        ):
            self.ended_at = ts
        return True

    def force_terminal(self, target: RunState, reason: str = "") -> None:
        """Force a terminal state (for error paths)."""
        ts = _utc_now()
        self.transitions.append(
            StateTransition(
                from_state=self.state.value,
                to_state=target.value,
                timestamp_utc=ts,
                reason=f"FORCED: {reason}",
            )
        )
        self.state = target
        self.ended_at = ts

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.BLOCKED,
            RunState.ABORTED,
        )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "profile_id": self.profile_id,
            "state": self.state.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "dry_run": self.dry_run,
            "transitions": [
                {
                    "from": t.from_state,
                    "to": t.to_state,
                    "ts": t.timestamp_utc,
                    "reason": t.reason,
                }
                for t in self.transitions
            ],
        }
