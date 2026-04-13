# Kommunikation & Daten - Technical Overview

**Root**: `23_compliance` | **Shard**: `04_kommunikation_daten`

## Scope

Handles communication and data exchange within the Compliance layer.
All operations are non-custodial and hash-only compliant.

## Key Components

- `kommunikation_daten_module.py`: Core ComplianceChecker implementation
- `chart.yaml`: Capability and policy definitions
- Evidence trail via SHA-256 hash ledger

## Integration Points

| Direction | Target | Protocol |
|-----------|--------|----------|
| Inbound   | 03_core | Internal API |
| Outbound  | 17_observability | Log sink |
| Outbound  | 23_compliance | Evidence target |
