# ADR 0002: Repo Separation Guard (Git-Independent Determinism)

## Status
Accepted

## Context
- Repo separation enforcement must work in Git worktree mode and ZIP/local mode without `.git`.
- Change-control and secret prevention must remain hard-fail and auditable.

## Decision
- `repo_separation_guard.py` enforces deterministic checks without requiring Git.
- In Git mode, changed-file detection tries:
  - `origin/<base_ref>...HEAD`
  - `<base_ref>...HEAD`
  - `HEAD~1...HEAD`
- In Git mode, path/secret checks run on tracked files (`git ls-files`).
- In non-Git mode, path/secret checks and ADR diff checks use `patch.diff` only.
- If no deterministic changed-file source exists (non-Git without `patch.diff`, or Git diff failure without `patch.diff`), guard returns tooling error.
- Exit codes are fixed:
  - `0` PASS
  - `2` policy violation
  - `3` tooling error

## Acceptance
- Guard returns only `PASS` or `FAIL` plus violation paths.
- Non-Git execution remains deterministic.
- Secret-like files and forbidden local-only paths are blocked.
- ADR requirement remains enforced for governance/structure/process-triggered changes.
