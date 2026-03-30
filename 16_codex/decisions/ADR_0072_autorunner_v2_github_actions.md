# ADR-0072: AutoRunner V2 — GitHub Actions Workflows (Plan A)

**Status:** Accepted
**Date:** 2026-03-16
**Author:** AutoRunner V2 Plan A (feat/autorunner-v2-plan-a)

## Context

Plan A of AutoRunner V2 introduces four deterministic GitHub Actions gate
workflows to enforce structural integrity, security, and contract compliance
on every push and PR targeting `main`:

- `AR-07 Forbidden Extensions Gate` (`.github/workflows/forbidden_extensions.yml`)
- `AR-08 OpenCore Sync Gate` (`.github/workflows/opencore_sync.yml`)
- `AR-02 Contract Tests Gate` (`.github/workflows/contract_tests.yml`)
- `AR-05 Shard Completion Gate` (`.github/workflows/shard_completion_gate.yml`)

These workflows are fully deterministic — they invoke only Python scripts
without Claude Agent calls. All evidence is uploaded as GitHub Actions
artifacts (90-day retention).

## Decision

Add the four Plan A AutoRunner workflows to `.github/workflows/`. Each
workflow is self-contained, idempotent, and exits with code 1 on gate
failure to block PR merge.

Test files are placed under `12_tooling/tests/autorunners/` (within the
ROOT-24-LOCK boundary), registered in `pytest.ini` testpaths.

Missing `07_governance_legal/` files required by SOT rules 024–027 are
created as canonical stubs.

## Consequences

- Four new CI gates enforce structural, security, and contract invariants
- All PRs to `main` must pass the new gates
- Test directory is `12_tooling/tests/autorunners/` (not root-level `tests/`)
- SOT contract check (AR-02) will pass once governance stubs are present

## Compliance

Supersedes: None
References: `16_codex/contracts/sot/sot_contract.yaml` rules 001–036,
`16_codex/ssid_master_definition_corrected_v1.1.1.md` §6, §7
