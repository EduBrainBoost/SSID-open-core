# Identitaet & Personen - Technical Overview

**Root**: `24_meta_orchestration` | **Shard**: `01_identitaet_personen`

## Scope

Handles identity and person management within the Meta-Orchestration layer.
All operations are non-custodial and hash-only compliant.

## Key Components

- `identitaet_personen_module.py`: Core OrchestrationCoordinator implementation
- `chart.yaml`: Capability and policy definitions
- Evidence trail via SHA-256 hash ledger

## Integration Points

| Direction | Target | Protocol |
|-----------|--------|----------|
| Inbound   | 03_core | Internal API |
| Outbound  | 17_observability | Log sink |
| Outbound  | 23_compliance | Evidence target |
