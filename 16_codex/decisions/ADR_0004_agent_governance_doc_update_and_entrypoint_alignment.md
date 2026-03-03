# ADR 0004: Agent-Governance Doc Update + Entrypoint Alignment


## Status
Accepted


## Context
- Changes to agent/governance documentation triggered ADR requirement via repo separation guard.
- Entrypoint has been standardized to 12_tooling/cli/ssid_dispatcher.py; canonical dispatcher remains under 24_meta_orchestration/dispatcher/.


## Decision
- Document updates that affect governance/process/structure require an ADR in the same change set.
- Entrypoint is defined as 12_tooling/cli/ssid_dispatcher.py.
- Root does not carry dispatcher wrappers; canonical dispatcher remains module-scoped.


## Consequences
- Prevents silent process drift.
- Keeps entrypoint changes auditable.