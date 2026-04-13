# 24_meta_orchestration/04_kommunikation_daten

## Purpose

Meta-Orchestration layer for communication and data exchange within the SSID ecosystem.
This shard provides cross-root orchestration, task dispatch, evidence collection specifically scoped to Kommunikation & Daten.

## Structure

```
04_kommunikation_daten/
  chart.yaml          - Shard capability definition (SoT)
  manifest.yaml       - Deployment manifest
  docs/               - Technical documentation
  tests/              - Test suites
  implementations/    - Language-specific implementations
    python/src/       - Python modules
```

## Interfaces

- **Inbound**: Receives requests from `03_core` and `24_meta_orchestration`
- **Outbound**: Emits evidence to `23_compliance`, logs to `17_observability`
- **Data**: Hash-only, non-custodial architecture (no PII storage)

## Policies

- `hash_only`: No PII stored; proofs and SHA-256 hashes only
- `non_custodial`: No custody; peer-to-peer flows; autonomous smart contracts
