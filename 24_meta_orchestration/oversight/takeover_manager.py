"""
Takeover Manager — Agent takeover orchestration with evidence logging.

Handles the lifecycle of one agent taking over responsibilities from another.
stdlib-only, deterministic, fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Takeover states (deterministic FSM)
# ---------------------------------------------------------------------------


class TakeoverState(Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class TakeoverReason(Enum):
    DEAD_AGENT = "DEAD_AGENT"
    STALE_AGENT = "STALE_AGENT"
    LOOP_DETECTED = "LOOP_DETECTED"
    DEGRADED_PERFORMANCE = "DEGRADED_PERFORMANCE"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


# ---------------------------------------------------------------------------
# Takeover event
# ---------------------------------------------------------------------------


@dataclass
class TakeoverEvent:
    """Immutable record of a takeover action."""

    event_id: str
    source_agent: str  # agent initiating takeover (watchdog)
    target_agent: str  # agent being taken over
    reason: str
    state: TakeoverState = TakeoverState.PROPOSED
    timestamp_utc: str = ""
    completed_utc: str = ""
    evidence_hash: str = ""
    error_detail: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp_utc:
            self.timestamp_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Takeover Manager
# ---------------------------------------------------------------------------


class TakeoverManager:
    """
    Manages the lifecycle of agent takeovers.
    Fail-closed: invalid state transitions raise.
    """

    def __init__(self, evidence_dir: str) -> None:
        self._evidence_dir = evidence_dir
        self._events: dict[str, TakeoverEvent] = {}
        self._event_counter = 0

    def _generate_event_id(self) -> str:
        self._event_counter += 1
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return f"takeover_{ts}_{self._event_counter:04d}"

    def initiate_takeover(
        self,
        source_agent: str,
        target_agent: str,
        reason: str,
    ) -> TakeoverEvent:
        """
        Initiate a takeover proposal.

        Fail-closed:
        - source == target -> raises
        - empty source/target -> raises
        """
        if not source_agent or not target_agent:
            raise ValueError("FAIL-CLOSED: source_agent and target_agent must be non-empty")
        if source_agent == target_agent:
            raise ValueError("FAIL-CLOSED: Agent cannot take over itself")

        event = TakeoverEvent(
            event_id=self._generate_event_id(),
            source_agent=source_agent,
            target_agent=target_agent,
            reason=reason,
            state=TakeoverState.PROPOSED,
        )
        self._events[event.event_id] = event
        return event

    def execute_takeover(self, event: TakeoverEvent) -> TakeoverEvent:
        """
        Execute a proposed takeover.

        State transitions:
        PROPOSED -> EXECUTING -> COMPLETED
        PROPOSED -> EXECUTING -> FAILED

        Fail-closed: wrong state -> raises.
        """
        if event.state != TakeoverState.PROPOSED:
            raise ValueError(f"FAIL-CLOSED: Cannot execute takeover in state {event.state.value}, expected PROPOSED")

        event.state = TakeoverState.EXECUTING

        try:
            # In a real system, this would:
            # 1. Acquire lock on target agent's scope
            # 2. Transfer active tasks to source agent
            # 3. Update registry state
            # For now: deterministic state transition
            event.state = TakeoverState.COMPLETED
            event.completed_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        except Exception as e:
            event.state = TakeoverState.FAILED
            event.error_detail = str(e)

        self._events[event.event_id] = event
        return event

    def log_takeover(self, event: TakeoverEvent) -> dict:
        """
        Write takeover evidence to the evidence directory.

        Returns the evidence record as dict.
        Fail-closed: unwritable evidence_dir -> raises.
        """
        evidence = {
            "event_id": event.event_id,
            "source_agent": event.source_agent,
            "target_agent": event.target_agent,
            "reason": event.reason,
            "state": event.state.value,
            "timestamp_utc": event.timestamp_utc,
            "completed_utc": event.completed_utc,
            "error_detail": event.error_detail,
        }

        # Compute SHA-256 of evidence content
        evidence_json = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
        sha256 = hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()
        evidence["sha256"] = sha256
        event.evidence_hash = sha256

        # Write evidence file
        os.makedirs(self._evidence_dir, exist_ok=True)
        evidence_path = os.path.join(self._evidence_dir, f"{event.event_id}.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2, ensure_ascii=False)

        return evidence

    def get_event(self, event_id: str) -> TakeoverEvent | None:
        return self._events.get(event_id)
