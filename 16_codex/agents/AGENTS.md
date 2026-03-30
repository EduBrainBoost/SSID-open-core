# AGENTS

Roles:
- Worker: modifies files only inside dispatcher-created sandbox/worktree.
- Gates: executes only real gate checks (`policy`, `sot`, `qa`, `duplicate-guard`).
- Integrator: applies patch to repo only after all gates PASS.

Hard rules:
- No direct repo writes by agents.
- No prompt/output/full-log persistence.
- No screenshots, DOM dumps, or secret storage.
- Audit output is minimal hash-only ledger in `02_audit_logging/agent_runs/`.
