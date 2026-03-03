# ADR-0053: Phase 2 Completion — Global Manifests, L3 Scaffold, Quarantine Hardening

Date: 2026-03-02
Status: Accepted
Decider: EduBrainBoost

## Context
After TS013+TS014 (manifest/conformance gates) and the Phase 2 baseline (shards registry,
pilot indices), three integration gaps remain before Level-3 readiness:
1. **TS015**: 382 non-pilot shards lack manifest.yaml (only 2 pilot shards had them)
2. **TS016/017**: No L3 scaffold (smoke tests + ARCHITECTURE.md) exists per root
3. **TS018**: Quarantine subsystem has no intake tooling, chain verification, or CI guard

## Decision
Add:
- **TS015 — Global manifest generation**: `shard_manifest_build.py --all --apply` to
  generate 382 manifest.yaml files for all non-pilot shards across 24 roots. Additive-only,
  never overwrites existing manifests. Shards registry regenerated to reflect new state.
- **TS016 — L3 scaffold system**:
  - Templates in `16_codex/templates/level3_root_scaffold/` (manifest.yaml, test_root_smoke.py.tpl, ARCHITECTURE.md.tpl)
  - Generator `12_tooling/cli/level3_scaffold.py` — idempotent, no-overwrite, renders per-root
  - 48 generated files: 24 `*/tests/test_root_smoke.py` + 24 `*/docs/ARCHITECTURE.md`
  - Gate `run_l3_scaffold_check()` added to `run_all_gates.py`
- **TS018 — Quarantine hardening**:
  - `12_tooling/cli/quarantine_intake.py` — strict reason-code allowlist (MALWARE, COMPROMISED_BINARY, ACTIVE_EXPLOIT_RISK, DMCA), append-only chain
  - `12_tooling/cli/quarantine_verify_chain.py` — validates chain integrity
  - `12_tooling/cli/quarantine_ci_guard.py` — enforces canonical quarantine paths in CI
  - `02_audit_logging/quarantine/hash_ledger/quarantine_chain.json` — genesis state
  - `23_compliance/evidence/malware_quarantine_hashes/.gitkeep` — evidence directory
  - Gate `run_quarantine_chain_verify()` added to `run_all_gates.py`
- **Gate chain update**: Policy -> SoT -> Shard -> Conformance -> Evidence -> L3 Scaffold -> Quarantine -> QA

## Consequences
- All 384 shards (24x16) now have manifest.yaml (full Hybrid-C coverage)
- Every root has smoke tests and architecture documentation (L3 baseline)
- Quarantine subsystem is hardened with append-only chain, CI guard, and evidence hashes
- Gate chain enforces all new invariants
- `shards_registry.json` and `sot_registry.json` updated to reflect new state
