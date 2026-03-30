"""
SSIDCTL v2 Profile Resolver + Agent Resolution Engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set

from .loader import AgentDef, ProfileDef, RegistryBundle


@dataclass
class ResolutionResult:
    profile_id: str
    resolved_agents: List[AgentDef]
    resolved_ids: FrozenSet[str]
    missing_deps: List[str]
    blocked: bool
    block_reason: str = ""


def resolve_profile(bundle: RegistryBundle, profile_id: str) -> ResolutionResult:
    """Resolve a profile to its concrete agent set with dependency validation."""
    if profile_id not in bundle.profiles:
        return ResolutionResult(
            profile_id=profile_id,
            resolved_agents=[],
            resolved_ids=frozenset(),
            missing_deps=[],
            blocked=True,
            block_reason=f"profile '{profile_id}' not found in registry",
        )

    profile = bundle.profiles[profile_id]
    agent_ids: Set[str] = set()

    # Collect agent IDs from profile
    if profile.agents == ["*"]:
        agent_ids = set(bundle.agents.keys())
    else:
        agent_ids.update(profile.agents)
        agent_ids.update(profile.phase_a_agents)
        agent_ids.update(profile.phase_b_agents)

    # Resolve agents
    resolved: List[AgentDef] = []
    missing_agents: List[str] = []
    for aid in sorted(agent_ids):
        if aid in bundle.agents:
            resolved.append(bundle.agents[aid])
        else:
            missing_agents.append(aid)

    if missing_agents:
        return ResolutionResult(
            profile_id=profile_id,
            resolved_agents=resolved,
            resolved_ids=frozenset(a.agent_id for a in resolved),
            missing_deps=missing_agents,
            blocked=True,
            block_reason=f"agents not in registry: {missing_agents}",
        )

    # Validate dependencies — deps must exist in the full registry (not just the profile)
    all_registry_ids = set(bundle.agents.keys())
    missing_deps: List[str] = []
    for agent in resolved:
        for dep in agent.depends_on:
            if dep not in all_registry_ids:
                missing_deps.append(f"{agent.agent_id} -> {dep}")

    if missing_deps:
        return ResolutionResult(
            profile_id=profile_id,
            resolved_agents=resolved,
            resolved_ids=frozenset(a.agent_id for a in resolved),
            missing_deps=missing_deps,
            blocked=True,
            block_reason=f"unresolved dependencies (not in registry): {missing_deps}",
        )

    return ResolutionResult(
        profile_id=profile_id,
        resolved_agents=resolved,
        resolved_ids=frozenset(a.agent_id for a in resolved),
        missing_deps=[],
        blocked=False,
    )


def filter_by_repo_scope(
    agents: List[AgentDef], repo: str
) -> List[AgentDef]:
    """Filter agents to those whose repo_scope includes the given repo."""
    return [a for a in agents if repo in a.repo_scope or "*" in a.repo_scope]


def filter_by_level(agents: List[AgentDef], level: str) -> List[AgentDef]:
    return [a for a in agents if a.level == level]


def get_activation_order(agents: List[AgentDef]) -> List[AgentDef]:
    """Return agents in deterministic activation order: L0, L1, L2, L3, L4, L5."""
    level_order = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
    return sorted(agents, key=lambda a: (level_order.get(a.level, 99), a.agent_id))
