# ADR-0060: Interfederation SPEC-ONLY SoT Verification

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `12_tooling/cli/`, `11_test_simulation/tests_compliance/`, `24_meta_orchestration/registry/`

## Context

The SoT validator (`sot_validator.py`) and gate runner (`run_all_gates.py`) need
to enforce the interfederation SPEC-ONLY boundary. Any path referencing
`23_compliance/evidence/interfederation_proofs/` must be validated as SPEC-ONLY
status, preventing premature claims of active interfederation.

## Decision

1. Extend `sot_validator.py` with `--verify-all` path guard logic that detects
   interfederation proof paths and validates their SPEC-ONLY status.
2. Add interfederation SPEC-ONLY guard step in `run_all_gates.py` gate chain.
3. Add tests in `test_sot_validator.py` covering the SPEC-ONLY path guard.
4. Update `sot_registry.json` hashes for all modified SoT artifacts.

## Consequences

- Interfederation proof paths are guarded at the SoT validation layer.
- Gate chain rejects invalid interfederation state claims automatically.
- SoT registry hashes stay in sync with modified artifacts.
- Output is PASS/FAIL + findings only (no scores).
