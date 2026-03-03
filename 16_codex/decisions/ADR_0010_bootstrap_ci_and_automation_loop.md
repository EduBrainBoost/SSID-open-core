# ADR 0010: Bootstrap CI Pipeline and Automation Loop Framework

## Status
Accepted

## Date
2026-02-27

## Context
SSID requires a deterministic, PR-only, evidence-based CI/CD workflow.
Prior to this change, CI gates existed but lacked a unified TaskSpec-driven
agent run framework, a stop-on-first-failure stability gate, and structured
evidence collection. The bootstrap PR introduces these components to enable
scoped, auditable agent work via the automation loop.

## Decision
1. Add `12_tooling/cli/automation_loop.py` as the TaskSpec-driven run framework
   with subcommands: `--verify-spec`, `--init`, `--start`, `--finalize`.
2. Add `12_tooling/cli/stability_gate.py` as the 5-gate PR readiness check
   (ROOT-24-LOCK, Git Clean, SoT Verify, pytest, Evidence Write).
3. Unify `.github/workflows/ssid_ci.yml` to run the full gate chain,
   stability gate, SoT validation, pytest, secret scan (Gitleaks), and
   evidence collection in a single workflow.
4. Add three proof-of-concept TaskSpecs under `24_meta_orchestration/tasks/specs/`
   to validate the framework post-merge.
5. Add `.github/CODEOWNERS` and `.github/pull_request_template.md` for
   PR governance. Update extension allowlist and path globs accordingly.
6. Add Docker toolchain under `15_infra/docker/` for deterministic CI builds.

## Constraints
- No new root-level directories (ROOT-24-LOCK preserved).
- CI does NOT run `--finalize`; finalization is local-only.
- All evidence is hash-only; no agent stdout/stderr persisted.
- TaskSpecs enforce `forbidden_paths` including `./`, `/mnt/data`, `**/.git/**`, `**/secrets/**`.
- Stop-on-first-failure semantics throughout the gate chain.

## Evidence
- `structure_guard.py` passes with 24 root modules.
- `stability_gate.py --run` passes all 5 gates.
- `sot_validator.py --verify-all` passes.
- `pytest -q` passes all tests (23 collected).

## Consequences
1. All future agent work follows TaskSpec -> AgentRun -> Patch/PR -> Gates -> Merge flow.
2. CI is blocking; PRs cannot merge without all gates passing.
3. The automation loop provides WORM evidence archives for auditability.
4. Three proof TaskSpecs demonstrate the framework works end-to-end.
