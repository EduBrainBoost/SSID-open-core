# SSID Agent Layer Model

## Status

Canonical reference document. Approved 2026-03-29.

## Overview

The SSID Agent Swarm operates on a **3-layer architecture** that intentionally separates logical agent definitions from runtime instantiation. The observation that 86 logical agents exist in the registry while only ~10 runtime containers are visible in a live swarm is **by design**, not a defect.

## The Three Layers

### Layer 1 -- Logical Agent Catalog (86 agents)

**Source:** `24_meta_orchestration/agentswarm/registry/agent_registry.yaml`

The logical layer is the complete catalog of every agent identity the system recognizes. Each entry defines:

- `agent_id` -- unique identifier (e.g. `agentswarm.execution.auth_runtime.primary`)
- `agent_role` -- primary or sentinel
- `pair_id` -- reference to the operational pair
- `group_type` -- orchestrator (24), execution (38), or control (24)
- `domain` -- functional area (runtime, frontend, backend, auth, policy, etc.)
- `repo_scope`, `branch_scope`, `worktree_scope` -- access boundaries
- `allowed_tools` / `denied_tools` -- tool permissions
- `required_skills` -- skill requirements
- `evidence_targets` -- audit trail paths
- `risk_level`, `approval_behavior` -- governance controls
- `can_write`, `can_delegate` -- capability flags

**Purpose:** The logical layer is the single source of truth for agent identity, permissions, and policy. Every agent that *could* run must be defined here. Agents not in this registry do not exist.

**Group breakdown:**

| Group | Count | Role |
|-------|-------|------|
| Orchestrator | 24 agents (12 pairs) | Domain coordination, scheduling, handoff |
| Execution | 38 agents (19 pairs) | Task execution, builds, tests, proofs |
| Control | 24 agents (12 pairs) | Guardrails, policy enforcement, monitoring |

### Layer 2 -- Operational Pairs (43 pairs)

**Source:** `24_meta_orchestration/agentswarm/registry/pair_registry.yaml`

The operational layer groups logical agents into primary/sentinel pairs. Each pair defines:

- `pair_id` -- unique pair identifier (e.g. `pair.orchestrator.runtime`)
- `primary_agent_id` -- the agent that executes work
- `sentinel_agent_id` -- the agent that monitors the primary
- `arbitration_mode` -- always `sentinel_monitors_primary`
- `heartbeat_policy_ref` -- liveness check policy
- `stagnation_policy_ref` -- stuck-detection policy
- `takeover_policy_ref` -- failover rules
- `fail_closed_on` -- conditions that trigger pair shutdown

**Purpose:** The pair model ensures every active agent has an independent monitor. The sentinel cannot write, push, merge, or create PRs -- it can only observe and trigger takeover if the primary violates policy. This is the SSID dual-control principle.

**Pair breakdown:**

| Group | Pairs | Domains |
|-------|-------|---------|
| Orchestrator | 12 | runtime, frontend, backend, orchestrator, provider, queue, policy, registry, audit, browser, release, repair |
| Execution | 19 | auth_runtime, routing_runtime, console_runtime, autorunner_runtime, eventflow_runtime, registry_sync, skill_sync, agent_registry, task_factory, root24_guard, sot_parity, build_executor, unit_test_executor, integration_test_executor, e2e_executor, browser_proof, observability_proof, docs_proof, rollback_repair |
| Control | 12 | loop_detection, timeout_control, takeover_manager, policy_drift, permissions_guard, evidence_integrity, result_verifier, concurrency_guard, cost_guard, memory_guard, incident_manager, worktree_guard |

### Layer 3 -- Runtime Projection (~10 containers)

**Source:** `24_meta_orchestration/agentswarm/registry/runtime_projection.yaml`

The runtime layer defines which logical agents are actually instantiated as containers or processes at any given time. Not every logical agent needs a runtime instance.

**Runtime modes:**

| Mode | Description |
|------|-------------|
| `always-on` | Permanent container/process, started with the swarm |
| `on-demand` | Instantiated when a task requires it, torn down after |
| `deferred` | Not instantiated until explicitly activated by an operator |
| `embedded` | Logic runs inside another agent's container (no own process) |

**Why 86 != 10:**

1. **Sentinels share runtime** -- A sentinel does not need its own container. It runs as a sidecar or embedded check within the primary's runtime context.
2. **On-demand agents sleep** -- Execution agents like `build_executor` or `e2e_executor` only spin up when builds or tests are triggered.
3. **Control agents are embedded** -- Guardrail agents (loop_detection, cost_guard, etc.) run as policy checks within the orchestrator runtime, not as separate containers.
4. **Domain consolidation** -- Multiple logical agents may share a single runtime container when their domains overlap.

## Invariants

1. Every runtime instance MUST map to at least one logical agent in `agent_registry.yaml`.
2. No runtime instance may exist without a corresponding pair in `pair_registry.yaml`.
3. The `runtime_projection.yaml` is the authoritative mapping from logical to runtime.
4. Adding a new runtime instance requires updating all three registries.
5. The logical agent count (86) is expected to grow independently of the runtime count (~10).

## References

- `24_meta_orchestration/agentswarm/registry/agent_registry.yaml` -- Logical agent catalog
- `24_meta_orchestration/agentswarm/registry/pair_registry.yaml` -- Operational pair registry
- `24_meta_orchestration/agentswarm/registry/runtime_projection.yaml` -- Runtime projection map
- `05_documentation/agents/SSID_AGENT_LAYER_ARCHITECTURE.md` -- External architecture doc
