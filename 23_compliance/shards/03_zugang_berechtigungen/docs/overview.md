# Zugang & Berechtigungen - Technical Overview

**Root**: `23_compliance` | **Shard**: `03_zugang_berechtigungen`

## Scope

Handles access control and authorization within the Compliance layer.
All operations are non-custodial and hash-only compliant.

## Key Components

- `zugang_berechtigungen_module.py`: Core ComplianceChecker implementation
- `chart.yaml`: Capability and policy definitions
- Evidence trail via SHA-256 hash ledger

## Integration Points

| Direction | Target | Protocol |
|-----------|--------|----------|
| Inbound   | 03_core | Internal API |
| Outbound  | 17_observability | Log sink |
| Outbound  | 23_compliance | Evidence target |
