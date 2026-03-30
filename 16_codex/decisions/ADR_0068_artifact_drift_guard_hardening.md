# ADR_0068: Artifact Drift Guard Hardening

## Status
Accepted

## Context
`repo_separation_guard.py` used only `HEAD~1` as fallback when `GITHUB_BASE_REF` was absent
(e.g. `workflow_dispatch`), missing commits between fork point and HEAD.
`run_all_gates.py` injected `GITHUB_BASE_REF=main` as a workaround.

## Decision
- Use `git merge-base HEAD origin/main` as deterministic fallback in repo_separation_guard.
- Remove `GITHUB_BASE_REF=main` injection from run_all_gates.py (guard is now self-sufficient).
- Fix Windows path separator in test_interfederation_claims_guard run-merge exempt pattern.
- Update sot_registry.json hash for run_all_gates.py.

## Consequences
- Positive: Guard captures all branch commits regardless of CI trigger mode.
- Positive: Eliminates hardcoded env-var workaround in gate runner.
- Negative: None identified.
