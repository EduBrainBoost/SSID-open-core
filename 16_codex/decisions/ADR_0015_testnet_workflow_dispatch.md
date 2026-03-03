# ADR-0015: Testnet MVP workflow_dispatch Workflow

## Status
Accepted

## Context
Phase-3 Testnet MVP scripts (deploy, verify, e2e) are merged and need a
GitHub Actions trigger to run against a real testnet. The workflow must be
manual-only (workflow_dispatch) to prevent accidental mainnet interaction,
and must use GitHub Environment secrets exclusively.

## Decision
Add `.github/workflows/testnet_mvp.yml` with:
- `workflow_dispatch` trigger only (no push/PR triggers)
- `permissions: contents: read` (minimal)
- `concurrency: testnet-mvp` (no parallel deploys)
- `environment: testnet` (secrets scoped to that environment)
- Secret mapping: `SSID_TESTNET_RPC_URL` -> `RPC_URL`, etc.
- Upload artifacts (deployment.json, verify_report.json, test_report.md)
- No commits back to the repository

## Consequences
- Testnet E2E can be triggered manually from Actions tab or `gh workflow run`
- Secrets remain in GitHub Environment, never in repo or logs
- Prod/mainnet keys stay local-only per ADR-0012
