# ADR-0052: Phase 2 — Shards Registry, Pilot Indices, and Evidence Completeness

Date: 2026-03-02
Status: Accepted
Decider: EduBrainBoost

## Context
After TS013+TS014 established manifest generation and conformance gates for pilot
shards, the next step (Phase 2) requires:
1. A shards registry (`shards_registry.json`) to track discovered shards across all roots
2. Pilot index files for conformance, contracts, and evidence per shard
3. A QA master suite (`test_pilot_conformance.py`) in the audit archive
4. Integration of shards registry build into the gate chain

## Decision
Add:
- `12_tooling/cli/shards_registry_build.py` — discovers chart.yaml + manifest.yaml
  across all roots, builds `shards_registry.json` with `--all --verify --source`
- `24_meta_orchestration/registry/shards_registry.json` — machine-readable shard index
- Pilot shard index files (`index.yaml`) for:
  - `03_core/shards/01_identitaet_personen/{conformance,contracts,evidence}/`
  - `03_core/shards/02_dokumente_nachweise/{conformance,contracts,evidence}/`
- `02_audit_logging/archives/qa_master_suite/test_pilot_conformance.py`
- `run_all_gates.py` updated to include shards registry verification

## Consequences
- Shards are discoverable via registry (enables future automation/scaling)
- Index files provide per-shard metadata for conformance and evidence tracking
- QA master suite archived for audit reference
- Gate chain now verifies shards registry consistency
