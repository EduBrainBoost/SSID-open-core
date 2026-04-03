# ADR-0083: Dispatcher Core Implementation — Audit Remediation

- **Status:** accepted
- **Date:** 2026-04-01
- **Scope:** `24_meta_orchestration/dispatcher/dispatcher.py`
- **Phase:** PROMPT 1 Audit & Remediation

## Context

The dispatcher was identified as a missing critical component during PROMPT 1 audit of SoT conformance. The 24×16 Shard matrix and ROOT-24-LOCK verification requires a lightweight, non-interactive dispatcher entry point that can validate repository structure before task orchestration.

## Decision

Implement `dispatcher.py` as the canonical dispatcher entry point at `24_meta_orchestration/dispatcher/dispatcher.py` with the following guarantees:

1. **Non-Interactive Execution** — CLI-only, no REPL or prompts. All behavior is controlled via command-line arguments.

2. **ROOT-24-LOCK Verification** — Exports a `verify_config()` function that validates exactly 24 root directories (01_ai_layer through 24_meta_orchestration) and rejects any unauthorized root-level items.

3. **Blueprint 4.1 Conformance** — Implements standard Dispatcher API (--version, --help, and custom --verify-config flag).

4. **SAFE-FIX Alignment** — No destructive operations. Only reads repository structure and reports findings.

5. **Smoke Test Validation** — All CLI paths (--version, --verify-config) execute without error.

## Consequences

- **Positive**: Dispatcher artifact is now auditable and can be integrated into run_all_gates.py verification workflow.
- **Positive**: ROOT-24-LOCK validation is now deterministic and repeatable.
- **Positive**: Blocks downstream PROMPT 2 agent-swarm execution until PROMPT 1 achieves PASS.

- **Constraint**: Dispatcher implementation must remain minimal (Blueprint 4.1) until full orchestration engine is specified via RFC.
- **Constraint**: Changes to dispatcher require corresponding RFC + ADR cycle before merge to main.

## Implementation Notes

- File: `24_meta_orchestration/dispatcher/dispatcher.py`
- Smoke tests: `python dispatcher.py --version` and `python dispatcher.py --verify-config`
- Expected exit codes: 0 (success), 1 (ROOT-24-LOCK violation), other (unexpected errors)
