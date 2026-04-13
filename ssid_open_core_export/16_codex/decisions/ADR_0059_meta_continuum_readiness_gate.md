# ADR-0059: Meta-Continuum Readiness Gate

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `12_tooling/cli/`, `23_compliance/policies/meta_continuum/`, `24_meta_orchestration/registry/`

## Context

SSID's meta-continuum concept is currently SPEC-ONLY / NOT_READY.
A formal gate is needed to evaluate and enforce readiness criteria,
preventing premature claims of meta-continuum capability.

## Decision

1. Add `23_compliance/policies/meta_continuum/readiness_config.yaml` defining
   6 readiness criteria (MC-01 through MC-06) with explicit MET/NOT_MET status.
2. Add `12_tooling/cli/meta_continuum_readiness.py` — gate tool that evaluates
   each criterion and reports PASS (gate evaluated correctly) with readiness
   status (READY or NOT_READY).
3. Wire readiness gate into `run_all_gates.py` after the interfederation
   claims guard gate.
4. Update `sot_registry.json` hash for the modified gate runner.
5. Add tests in `test_meta_continuum_readiness.py`.

The gate PASSES when it can correctly determine the system's readiness state.
Currently: NOT_READY (MC-01 proof snapshot and MC-06 external handshake
are NOT_MET). This is the expected single-system state.

## Consequences

- Meta-continuum readiness is evaluated automatically in the gate chain.
- Advancement requires ALL 6 criteria MET (no partial advancement).
- SoT registry stays in sync with the actual gate runner file.
- Output is PASS/FAIL + findings only (no scores).
