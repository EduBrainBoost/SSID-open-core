"""
Agent Oversight Graph — Watchdog Assignment & Escalation Chains.

Builds a directed oversight graph from the 87-agent registry.
Each agent's `depends_on` field defines its watchdog (supervisor).
L0 master_orchestrator is self-watching (root sentinel).

stdlib-only, deterministic, fail-closed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WatchdogAssignment:
    """Maps an agent to its watchdog (supervisor)."""

    agent_id: str
    watchdog_agent_id: str


@dataclass
class OversightGraph:
    """Directed graph: agent -> watchdog, plus reverse index."""

    assignments: dict[str, WatchdogAssignment] = field(default_factory=dict)
    # reverse: watchdog -> list of agents it supervises
    supervised_by: dict[str, list[str]] = field(default_factory=dict)

    def get_watchdog(self, agent_id: str) -> str | None:
        a = self.assignments.get(agent_id)
        return a.watchdog_agent_id if a else None

    def get_supervised(self, watchdog_id: str) -> list[str]:
        return list(self.supervised_by.get(watchdog_id, []))


# ---------------------------------------------------------------------------
# Registry loader (YAML via stdlib — parse the simple subset we need)
# ---------------------------------------------------------------------------


def _load_registry_agents(registry_path: str) -> list[dict]:
    """Load agents from the v2 YAML registry using json sidecar or minimal parse."""
    json_path = registry_path.replace(".yaml", ".json")
    if os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("agents", [])

    # Fallback: minimal YAML-subset parser for agent_id + depends_on + level
    agents = []
    current: dict | None = None
    with open(registry_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if stripped.startswith("- agent_id:"):
                if current is not None:
                    agents.append(current)
                current = {
                    "agent_id": stripped.split(":", 1)[1].strip(),
                    "depends_on": [],
                    "level": "",
                    "status": "active",
                }
            elif current is not None:
                if stripped.strip().startswith("level:"):
                    current["level"] = stripped.split(":", 1)[1].strip()
                elif stripped.strip().startswith("status:"):
                    current["status"] = stripped.split(":", 1)[1].strip()
                elif stripped.strip().startswith("- ssidctl."):
                    # depends_on entries
                    current["depends_on"].append(stripped.strip().lstrip("- "))
    if current is not None:
        agents.append(current)
    return agents


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

L0_SENTINEL = "ssidctl.l0.master_orchestrator"


def build_oversight_graph(registry_path: str) -> OversightGraph:
    """
    Build the full oversight graph from the agent registry.

    Rules:
    - Each agent's primary watchdog is its first `depends_on` entry.
    - If `depends_on` is empty, the watchdog is the L0 master orchestrator.
    - L0 master orchestrator watches itself (root sentinel).
    - Only active agents are included.

    Fail-closed: if registry cannot be loaded, raises.
    """
    agents = _load_registry_agents(registry_path)
    if not agents:
        raise ValueError(f"FAIL-CLOSED: No agents loaded from {registry_path}")

    graph = OversightGraph()

    for agent in agents:
        if agent.get("status", "active") != "active":
            continue

        agent_id = agent["agent_id"]
        depends = agent.get("depends_on", [])

        if agent_id == L0_SENTINEL:
            # Root sentinel watches itself
            watchdog_id = L0_SENTINEL
        elif depends:
            watchdog_id = depends[0]
        else:
            # Fail-closed: no dependency -> escalate to L0
            watchdog_id = L0_SENTINEL

        assignment = WatchdogAssignment(
            agent_id=agent_id,
            watchdog_agent_id=watchdog_id,
        )
        graph.assignments[agent_id] = assignment

        if watchdog_id not in graph.supervised_by:
            graph.supervised_by[watchdog_id] = []
        graph.supervised_by[watchdog_id].append(agent_id)

    return graph


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------


def validate_no_unwatched(graph: OversightGraph) -> bool:
    """
    Validate that every agent in the graph has a watchdog assigned.
    Returns True if invariant holds, False otherwise.
    Fail-closed: empty graph returns False.
    """
    if not graph.assignments:
        return False

    for agent_id, assignment in graph.assignments.items():
        if not assignment.watchdog_agent_id:
            return False
        # Watchdog must also be a known agent (except self-watch for L0)
        if assignment.watchdog_agent_id != agent_id and assignment.watchdog_agent_id not in graph.assignments:
            return False
    return True


def get_escalation_chain(graph: OversightGraph, agent_id: str) -> list[str]:
    """
    Get the escalation chain for an agent: agent -> watchdog -> watchdog's watchdog -> ... -> L0.

    Returns list starting with agent_id and ending with L0_SENTINEL.
    Fail-closed: if cycle detected (other than L0 self-loop), raises ValueError.
    Fail-closed: if agent_id not in graph, raises KeyError.
    """
    if agent_id not in graph.assignments:
        raise KeyError(f"FAIL-CLOSED: Agent '{agent_id}' not in oversight graph")

    chain = [agent_id]
    visited = {agent_id}
    current = agent_id

    while True:
        watchdog = graph.assignments[current].watchdog_agent_id
        if watchdog == current:
            # Self-loop: must be L0 sentinel
            if current != L0_SENTINEL:
                raise ValueError(f"FAIL-CLOSED: Non-L0 agent '{current}' has self-referencing watchdog")
            break

        if watchdog in visited:
            raise ValueError(f"FAIL-CLOSED: Cycle detected in escalation chain at '{watchdog}'")

        chain.append(watchdog)
        visited.add(watchdog)
        current = watchdog

    return chain
