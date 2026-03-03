# ADR 0014: Phase 3 Implementation TaskSpec Pack

## Status

Accepted

## Date

2026-02-28

## Context

PR #9 delivered five Phase 3 specification TaskSpecs for the Testnet MVP
(hash-only proof registry). To enable parallel implementation work, we
split execution into three focused PRs: artifacts, scripts, and
tests+docs. Each implementation PR maps to one or more Phase 3 specs.

These implementation TaskSpecs are stored under
`24_meta_orchestration/tasks/specs/`, triggering the ADR requirement
via `repo_separation_guard.py`.

## Decision

1. Create three implementation TaskSpecs under
   `24_meta_orchestration/tasks/specs/`:
   - **PH3_IMPL_ARTIFACTS_002**: Implements PH3_CONTRACT_ARTIFACTS_001.
     ABI, bytecode, compiler manifest, and spec with deterministic hashes.
   - **PH3_IMPL_SCRIPTS_002**: Implements PH3_DEPLOY_SCRIPT_001 and
     PH3_VERIFY_SCRIPT_001. deploy_testnet.py + verify_testnet.py with
     ENV-only secrets and redacted output.
   - **PH3_IMPL_TESTS_DOCS_002**: Implements PH3_E2E_PYTEST_001 and
     PH3_RUNBOOK_ENV_001. E2E pytest with testnet/slow marks and
     TESTNET_RUNBOOK.md with 1-command flow documentation.
2. No code, CI, or gate modifications are included in this changeset.
3. Specs are validated via `automation_loop.py --verify-spec`.

## Consequences

- Three parallel implementation PRs can begin immediately after merge.
- Each implementation PR has a clear scope and acceptance criteria.
- No .sol files in repo; secrets from ENV only; prod keys local-only.
