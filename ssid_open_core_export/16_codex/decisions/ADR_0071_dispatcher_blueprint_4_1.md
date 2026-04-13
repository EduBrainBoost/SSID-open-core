# ADR-0071: Dispatcher Blueprint 4.1 — Canonicalization

- **Status:** accepted
- **Date:** 2026-03-09
- **Scope:** `24_meta_orchestration/dispatcher/e2e_dispatcher.py`, `.gitignore`

## Context

The `e2e_dispatcher.py` evolved through several iterations on feature branches
with hardening improvements that were never canonicalized on main.
Blueprint 4.1 consolidates five improvements into a single merge-ready delta
(+97/−11 lines, 3 files).

## Decisions

1. **Health-Check Fast Path** — A `--health-check` CLI flag runs
   `_run_health_check()` which validates environment (SSID_EMS_STATE dir exists),
   prints `HEALTH_CHECK PASS`, and exits. This enables liveness probes without
   executing a full dispatch cycle.

2. **Task-ID Validation** — `_validate_task_id()` enforces a regex allowlist
   (`^[A-Za-z0-9_-]+$`) and rejects path-traversal sequences (`..`, `/`, `\`)
   before any filesystem operation. Prevents directory-traversal attacks via
   crafted task IDs.

3. **Write-Gate Bypass for Infra Paths** — `WRITE_GATE_BYPASS_PREFIXES`
   (`.claude/`, `.github/`) allows the dispatcher to write CI/CD and Claude
   configuration files without triggering the write-gate lock. These paths
   are infrastructure, not SoT content.

4. **Sandbox Externalization** — `SANDBOX_ROOT` moved from repo-internal
   `.ssid_sandbox/` to `$SSID_EMS_STATE/sandbox/`, keeping ephemeral run
   artifacts outside the SSID repo working tree. Prevents sandbox sprawl
   inside the SoT repo.

5. **Ignore-Rule for Health-Check Cleanup** — `.gitignore` updated with
   `**/health_check_cleanup/` pattern so WORM cleanup artifacts from
   health-check runs are never accidentally committed.

## Consequences

- No SoT or Root-24 drift: all changes stay within `24_meta_orchestration/`
  (dispatcher's canonical root) plus `.gitignore` (repo-level infra).
- Dispatcher CLI interface remains backward-compatible; `--health-check` is
  additive.
- Downstream consumers (EMS orchestrator, CI gates) require no repointing.
- **Prerequisite:** `SSID_EMS_STATE` environment variable must be set in any
  environment that runs the dispatcher outside of health-check mode.
