# ADR-0058: Interfederation Claims Guard

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `23_compliance/policies/`, `12_tooling/cli/`, `24_meta_orchestration/registry/`

## Context

SSID documents interfederation as SPEC-ONLY / BLOCKED. No bidirectional claims
(e.g., "interfederation active", "mutual validation complete") are permitted
without a cryptographic proof snapshot linking both repositories.

Changes to `24_meta_orchestration/registry/sot_registry.json` (SoT hash update
for `run_all_gates.py`) and new files under `23_compliance/policies/` and
`12_tooling/cli/` trigger the ADR-Pflicht and repo separation guard.

## Decision

1. Add `23_compliance/policies/claims_guard.rego` — Rego policy that denies
   forbidden interfederation claims unless a valid proof snapshot is present.
2. Add `12_tooling/cli/interfederation_proof.py` — CLI tool generating
   hash-only proof of current SSID state (commit SHA + file hashes).
   Status field is hard-coded to `SINGLE_SYSTEM_ONLY`.
3. Wire claims guard into `12_tooling/cli/run_all_gates.py` gate chain.
4. Update `sot_registry.json` hash for `run_all_gates.py` to reflect the
   modified gate chain.
5. Add compliance tests (`test_claims_guard.py`) and tool tests
   (`test_interfederation_proof.py`).

## Consequences

- Forbidden interfederation claims are detected and blocked automatically.
- Proof tool outputs hash-only data; no secrets or PII.
- SoT registry stays in sync with the actual gate runner file.
- Gate chain includes claims guard before policy check.
