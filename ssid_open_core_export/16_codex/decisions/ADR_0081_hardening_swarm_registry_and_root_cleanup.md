# ADR-0081: Hardening Swarm - Registry and Root Cleanup

**Status:** Accepted
**Date:** 2026-03-30
**Deciders:** A00 Integrator (Hardening Swarm)

## Context

The hardening swarm (hardening/swarm-20260330T194800Z) identified several structural
inconsistencies that violate ROOT-24-LOCK, registry logs policy, and SoT data-minimization
requirements.

## Decisions

### 1. Root-level `tasks/` directory removal
The `tasks/` directory at repo root violated ROOT-24-LOCK (only 24 canonical roots allowed).
Tracked files were moved to `12_tooling/tasks/`; untracked scratch files were moved to
Zone C (outside repo).

### 2. `.mailmap` added to root-level allowlist
`.mailmap` is a standard Git author-mapping file. Added to
`23_compliance/exceptions/root_level_exceptions.yaml`.

### 3. `requirements.lock` added to root24_daily_guard allowlist
`requirements.lock` is a reproducible-build artifact analogous to `pyproject.toml`.
Already allowed in `root_level_exceptions.yaml`; now also in `root24_daily_guard.py`.

### 4. Registry logs policy enforcement
`24_meta_orchestration/registry/logs/SSID_structure_level3_ref.md` was a pointer document,
not a log file. Moved to `24_meta_orchestration/registry/manifests/` to comply with
the logs policy (only `*.log` and `*.log.jsonl` in `registry/logs/`).

### 5. Runtime index files untracked
Empty `.jsonl` files (`execution_index.jsonl`, `plan_execution_index.jsonl`,
`taskspec_pr_index.jsonl`) were runtime artifacts appended by verify-runs.
Removed from git tracking and added to `.gitignore`.

### 6. ssid_dispatcher.py data-minimization markers
Added SOT_AGENT_044/045/046/048 compliance markers for log mode, prompt persistence,
stdout persistence, and sandbox cleanup policies.

### 7. Cache-noise .gitignore hardening
Added `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`, `dist/`, `build/` to `.gitignore`.

### 8. Canonical runbook created
`05_documentation/runbooks/RUNBOOK_CANONICAL_RUN.md` created as single-source
entry point for verification and gate pipeline runs.

## Consequences

- ROOT-24-LOCK fully enforced (24 roots, no extras)
- SoT validator passes all 48 rules
- Registry logs directory contains only log files
- Verify-runs no longer produce tracked file noise
