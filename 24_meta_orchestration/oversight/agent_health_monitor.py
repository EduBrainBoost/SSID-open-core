"""
Agent Health Monitor — Health checks, stagnation & loop detection.

Deterministic state machine for agent health.
stdlib-only, fail-closed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Health states (deterministic FSM)
# ---------------------------------------------------------------------------

class HealthState(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    DEAD = "DEAD"


# ---------------------------------------------------------------------------
# Agent state tracking
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    """Tracked state for a single agent."""
    agent_id: str
    last_heartbeat: float = 0.0  # UTC epoch seconds
    last_output_time: float = 0.0
    error_count: int = 0
    consecutive_errors: int = 0
    recent_errors: List[str] = field(default_factory=list)
    state: HealthState = HealthState.HEALTHY

    # Thresholds (seconds)
    stale_threshold: float = 300.0   # 5 min
    dead_threshold: float = 900.0    # 15 min
    degraded_error_count: int = 3
    max_recent_errors: int = 50


# ---------------------------------------------------------------------------
# Health Monitor
# ---------------------------------------------------------------------------

class AgentHealthMonitor:
    """
    Monitors agent health via heartbeats and error tracking.
    Fail-closed: unknown agent_id -> DEAD.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentState] = {}

    def register_agent(
        self,
        agent_id: str,
        stale_threshold: float = 300.0,
        dead_threshold: float = 900.0,
    ) -> None:
        now = time.time()
        self._agents[agent_id] = AgentState(
            agent_id=agent_id,
            last_heartbeat=now,
            last_output_time=now,
            stale_threshold=stale_threshold,
            dead_threshold=dead_threshold,
        )

    def record_heartbeat(self, agent_id: str) -> None:
        """Record that agent is alive."""
        if agent_id not in self._agents:
            return  # fail-closed: ignore unknown
        self._agents[agent_id].last_heartbeat = time.time()

    def record_output(self, agent_id: str) -> None:
        """Record that agent produced output."""
        if agent_id not in self._agents:
            return
        now = time.time()
        state = self._agents[agent_id]
        state.last_output_time = now
        state.last_heartbeat = now
        # Successful output resets consecutive error count
        state.consecutive_errors = 0

    def record_error(self, agent_id: str, error_signature: str) -> None:
        """Record an error from an agent."""
        if agent_id not in self._agents:
            return
        state = self._agents[agent_id]
        state.error_count += 1
        state.consecutive_errors += 1
        state.recent_errors.append(error_signature)
        if len(state.recent_errors) > state.max_recent_errors:
            state.recent_errors = state.recent_errors[-state.max_recent_errors:]

    def check_agent_health(self, agent_id: str) -> HealthState:
        """
        Check health of an agent. Deterministic FSM:

        DEAD:     unknown agent OR idle > dead_threshold
        STALE:    idle > stale_threshold
        DEGRADED: consecutive_errors >= degraded_error_count
        HEALTHY:  otherwise

        Fail-closed: unknown agent -> DEAD.
        """
        if agent_id not in self._agents:
            return HealthState.DEAD

        state = self._agents[agent_id]
        now = time.time()
        idle = now - state.last_heartbeat

        if idle > state.dead_threshold:
            state.state = HealthState.DEAD
        elif idle > state.stale_threshold:
            state.state = HealthState.STALE
        elif state.consecutive_errors >= state.degraded_error_count:
            state.state = HealthState.DEGRADED
        else:
            state.state = HealthState.HEALTHY

        return state.state

    def detect_stagnation(self, agent_id: str, max_idle_seconds: float) -> bool:
        """
        Detect if agent has been idle (no output) longer than max_idle_seconds.
        Fail-closed: unknown agent -> True (stagnant).
        """
        if agent_id not in self._agents:
            return True  # fail-closed

        state = self._agents[agent_id]
        idle = time.time() - state.last_output_time
        return idle > max_idle_seconds

    def detect_loop(self, agent_id: str, error_signatures: List[str]) -> bool:
        """
        Detect if agent is in an error loop: the same error signatures
        repeat consecutively in recent_errors.

        A loop is detected when the provided signature sequence appears
        at least twice consecutively in the recent error history.

        Fail-closed: unknown agent -> True (assume looping).
        """
        if agent_id not in self._agents:
            return True  # fail-closed

        state = self._agents[agent_id]
        if not error_signatures or not state.recent_errors:
            return False

        pattern_len = len(error_signatures)
        recent = state.recent_errors

        if len(recent) < pattern_len * 2:
            return False

        # Check if pattern appears at least twice consecutively at the tail
        tail = recent[-(pattern_len * 2):]
        first_occurrence = tail[:pattern_len]
        second_occurrence = tail[pattern_len:]

        return first_occurrence == error_signatures and second_occurrence == error_signatures

    def get_state(self, agent_id: str) -> Optional[AgentState]:
        return self._agents.get(agent_id)
