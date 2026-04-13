# ADR_0007_sot_registry_update

## Status
Accepted

## Context
A change was made to `24_meta_orchestration/registry/sot_registry.json`.
Per Repo Separation Guard policy, any change under `24_meta_orchestration/` requires an ADR in the same change-set.

## Decision
We document and accept the update to `sot_registry.json` as part of SoT registry maintenance.
This ADR exists solely to satisfy governance traceability requirements for changes under `24_meta_orchestration/`.

## Consequences
- Positive: Repo Separation Guard passes; traceability is preserved for registry changes.
- Negative: Additional governance overhead for purely mechanical registry updates.
