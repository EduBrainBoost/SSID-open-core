# SSID Multi-Agent CLI Stack (bootstrap)

Entry point: `24_meta_orchestration/dispatcher/e2e_dispatcher.py` via `12_tooling/cli/ssid_dispatcher.py`

## Quick validation
Run gates locally:
- `python3 12_tooling/cli/run_all_gates.py`
- `python3 12_tooling/cli/sot_validator.py --verify-all`

## Task-based usage (patch-only)
1) Create or edit a task spec (JSON):
   - `24_meta_orchestration/registry/tasks/TASK_BOOTSTRAP_AGENT_STACK.json`
2) Print the injected header (for any agent/tool):
   - `python3 12_tooling/cli/ssid_dispatcher.py package --task 24_meta_orchestration/registry/tasks/TASK_BOOTSTRAP_AGENT_STACK.json`
3) Run an agent wrapper inside sandbox (example):
   - `12_tooling/wrappers/codex_run.sh 24_meta_orchestration/registry/tasks/TASK_BOOTSTRAP_AGENT_STACK.json "<agent command here>"`
   - OpenAI Codex profile: `12_tooling/cli/config/codex_openai_profile.yaml`
   - Dedicated OpenAI runner: `12_tooling/wrappers/codex_openai_run.sh <task>.json "<codex command>"`
   - PowerShell runner: `12_tooling/wrappers/codex_openai_run.ps1 -Task <task>.json -Cmdline "<codex command>"`
4) Evidence bundle (hash-only) is written to:
   - `02_audit_logging/evidence/<task_id>/`

Data minimization:
- Prompts/stdout are not persisted in MINIMAL mode (default).
