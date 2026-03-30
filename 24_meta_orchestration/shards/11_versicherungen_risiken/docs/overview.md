# Versicherungen & Risiken - Technical Overview

**Root**: `24_meta_orchestration` | **Shard**: `11_versicherungen_risiken`

## Scope

Handles insurance and risk management within the Meta-Orchestration layer.
All operations are non-custodial and hash-only compliant.

## Key Components

- `versicherungen_risiken_module.py`: Core OrchestrationCoordinator implementation
- `chart.yaml`: Capability and policy definitions
- Evidence trail via SHA-256 hash ledger

## Integration Points

| Direction | Target | Protocol |
|-----------|--------|----------|
| Inbound   | 03_core | Internal API |
| Outbound  | 17_observability | Log sink |
| Outbound  | 23_compliance | Evidence target |
