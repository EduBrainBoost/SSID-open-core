# WORKFLOW

1. Plan-first: define task scope, allowlist, and hard limits in queue/task spec.
2. Patch-only: all edits happen in `.ssid_sandbox/<run_id>/<task_id>/`.
3. Gates-first: run `policy -> sot -> qa` with real checks only (no simulation).
4. Duplicate-Guard: hard-fail before merge/apply.
5. Integrate only on PASS: apply unified diff mechanically to repo.
6. Evidence minimal: write hash-only manifest per run in `02_audit_logging/agent_runs/<run_id>/manifest.json` (+ optional `patch.diff`).
7. Cleanup: remove `.ssid_sandbox` task run artifacts after completion.
