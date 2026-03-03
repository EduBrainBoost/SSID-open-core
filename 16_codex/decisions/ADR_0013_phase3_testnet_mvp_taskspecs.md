# ADR 0013: Phase 3 Testnet MVP TaskSpec Pack

## Status

Accepted

## Date

2026-02-28

## Context

Phase 2 established the automation loop E2E pipeline with four TaskSpecs.
Phase 3 targets the Testnet MVP: a hash-only proof registry deployed and
verified on a public testnet. This requires contract artifacts, deployment
and verification scripts, end-to-end tests, and an ENV runbook.

All five specs target `24_meta_orchestration/tasks/specs/` and the
TASK_QUEUE at `24_meta_orchestration/queue/`, which triggers the ADR
requirement via `repo_separation_guard.py`.

## Decision

1. Create five Phase 3 TaskSpecs under `24_meta_orchestration/tasks/specs/`:
   - **PH3_CONTRACT_ARTIFACTS_001**: ABI, bytecode, compiler manifest, and
     spec for the hash-only proof registry. No `.sol` files in repo.
   - **PH3_DEPLOY_SCRIPT_001**: Deterministic deploy script reading
     RPC_URL, CHAIN_ID, PRIVATE_KEY from ENV only. Redacted output.
   - **PH3_VERIFY_SCRIPT_001**: Round-trip verification script:
     hasProof(false) -> addProof -> hasProof(true). ENV-only secrets.
   - **PH3_E2E_PYTEST_001**: End-to-end pytest with `testnet`/`slow`
     marks, graceful skip when ENV vars are absent.
   - **PH3_RUNBOOK_ENV_001**: Runbook documenting ENV setup, GitHub
     Environment `testnet` policy, and 1-command deploy-verify-e2e flow.
2. Update `TASK_QUEUE.yaml` with Phase 3 task pointers referencing
   each spec file.
3. Each spec uses the established TaskSpec YAML format validated by
   `automation_loop.py --verify-spec`.
4. No code, CI, or gate modifications are included in this changeset.

## Consequences

- Phase 3 implementation PRs (artifacts, scripts, tests/docs) can begin
  after this spec pack merges.
- Contract is compiled externally; only artifacts are committed (no `.sol`).
- All secrets come from environment variables; no secret material in repo.
- Testnet tests are skippable in CI via pytest marks.
