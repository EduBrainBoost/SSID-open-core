# 23_compliance/12_immobilien_grundstuecke

## Purpose

Compliance layer for real estate and property within the SSID ecosystem.
This shard provides regulatory compliance checking, evidence emission, requirement mapping specifically scoped to Immobilien & Grundstuecke.

## Structure

```
12_immobilien_grundstuecke/
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
