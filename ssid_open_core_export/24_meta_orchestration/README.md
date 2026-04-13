# 24_meta_orchestration — Meta Orchestration & System Coordination

**Classification:** Orchestration — Central Coordination Authority
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Central orchestration and system coordination layer for the SSID platform. Manages
the agent swarm, dispatcher infrastructure, global registry, pipeline definitions,
incident management, oversight mechanisms, DAO treasury policy, and release
coordination. This is the operational command center that coordinates all 24 root
modules. Final authority resides with `03_core`.

This module does NOT:
- Store customer PII
- Define compliance policies (those reside in `23_compliance/`)
- Hold secrets or credentials

## Not Maintained Here

| Domain | Central Location |
|--------|-----------------|
| Compliance policies | `23_compliance/policies/` |
| SoT specifications | `16_codex/` |
| Audit evidence | `02_audit_logging/` |

## Structure

| Directory      | Purpose                                              |
|----------------|------------------------------------------------------|
| `docs/`        | Module-level documentation                            |
| `agents/`      | Agent definitions and configurations                  |
| `agentswarm/`  | Agent swarm coordination                              |
| `config/`      | Orchestration configuration                           |
| `contracts/`   | Orchestration contracts                               |
| `dispatcher/`  | Task dispatcher infrastructure                        |
| `incident/`    | Incident management and response                      |
| `monitoring/`  | System monitoring coordination                        |
| `oversight/`   | Oversight and control mechanisms                      |
| `pipelines/`   | Pipeline definitions and workflows                    |
| `plans/`       | Execution plans and coordination schedules            |
| `policies/`    | Module-internal orchestration policies                |
| `queue/`       | Task queue management                                 |
| `registry/`    | Global service and module registry                    |
| `releases/`    | Release coordination and versioning                   |
| `shards/`      | 16 domain shards                                      |

## Key Files

- `dao_treasury_policy.yaml` — DAO treasury governance policy

## Orchestration Principles

- **NON-INTERACTIVE:** Dispatcher operates in non-interactive mode
- **SAFE-FIX:** All writes are additive with evidence logging
- **Lock-enforced:** Session isolation with lock files per agent
- **Evidence-driven:** All orchestration decisions logged to audit trail

## Interfaces

| Direction | Central Path | Description |
|-----------|-------------|-------------|
| Output | `17_observability/logs/meta_orchestration/` | Log output specification |
| Output | `23_compliance/evidence/meta_orchestration/` | Evidence path (hash-only) |

## Governance

- **SOT_AGENT_063**: Structure conforms to MUST paths
- **SOT_AGENT_064**: No shadow files or forbidden copies
- **SOT_AGENT_065**: Interfaces reference central paths
