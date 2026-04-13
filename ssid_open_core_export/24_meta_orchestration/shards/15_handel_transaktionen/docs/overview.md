# Handel & Transaktionen - Technical Overview

**Root**: `24_meta_orchestration` | **Shard**: `15_handel_transaktionen`

## Scope

Handles trade and transaction processing within the Meta-Orchestration layer.
All operations are non-custodial and hash-only compliant.

## Key Components

- `handel_transaktionen_module.py`: Core OrchestrationCoordinator implementation
- `chart.yaml`: Capability and policy definitions
- Evidence trail via SHA-256 hash ledger

## Integration Points

| Direction | Target | Protocol |
|-----------|--------|----------|
| Inbound   | 03_core | Internal API |
| Outbound  | 17_observability | Log sink |
| Outbound  | 23_compliance | Evidence target |
