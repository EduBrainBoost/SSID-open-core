# ADR 0012: Phase 2 Automation Loop TaskSpec Pack

## Status

Accepted

## Date

2026-02-28

## Context

The bootstrap phase (PRs #1–#4) established the CI/CD workflow, automation loop,
stability gate, and three proof-of-concept TaskSpecs. To scale the automation
loop into a production-ready E2E pipeline, we need a structured set of Phase 2
TaskSpecs covering refactoring, testing, documentation, and end-to-end smoke
validation of the automation loop lifecycle.

All four specs target the `24_meta_orchestration/tasks/specs/` directory, which
triggers the ADR requirement via `repo_separation_guard.py`.

## Decision

1. Create four Phase 2 TaskSpecs under `24_meta_orchestration/tasks/specs/`:
   - **PH2_LOOP_REF_001**: Deterministic JSON output formatting (pure refactor).
   - **PH2_LOOP_TST_001**: Edge-case tests for spec validation and allowlist
     enforcement.
   - **PH2_LOOP_DOC_001**: Runbook with 1-command-per-task examples and
     Windows/WSL/Codespaces troubleshooting.
   - **PH2_LOOP_E2E_001**: Smoke E2E test verifying start→edit→finalize produces
     deterministic patch, evidence, and zip outputs.
2. Each spec uses the existing TaskSpec YAML format with `task_id`, `title`,
   `task_type`, `scope_allowlist`, `forbidden_paths`, `required_checks`,
   `acceptance_criteria`, and `evidence_outputs`.
3. No code, CI, or gate modifications are included in this changeset.
4. Specs are validated locally via `automation_loop.py --verify-spec`.

## Consequences

- Phase 2 execution PRs can begin immediately after this spec pack merges.
- Scopes are cleanly separated, enabling parallel worker execution.
- No production code is modified; risk is limited to spec correctness.
