# ADR 0012: GitHub as Execution Plane, Local as Key Plane

## Status

Accepted

## Date

2026-02-28

## Context

SSID requires a clear separation between where code is built/tested/deployed (execution) and where cryptographic keys are managed (key custody). Mixing these planes creates unacceptable risk: a compromised CI pipeline could exfiltrate signing keys, and keys stored in repository history are effectively public.

The project operates across two environments (testnet, mainnet) with different risk profiles. Testnet keys are ephemeral and low-value. Mainnet keys control real assets and identities.

Previous discussions considered three approaches:

1. Keys in CI — all secrets stored in GitHub, used directly by workflows.
2. Browser-only execution — signing and deployment done through browser-based tools, repository used only for source storage.
3. GitHub as execution plane, local as key plane — CI handles build/test/deploy orchestration, but mainnet signing happens locally on operator hardware.

## Decision

**GitHub is the Control and Execution Plane.** All code changes flow through PRs. CI (GitHub Actions) handles building, testing, gating, and testnet deployments. Workflow dispatch with environment gating controls deployment triggers.

**Local is the Key Plane.** Mainnet signing keys exist only on operator-controlled hardware (hardware wallets, air-gapped machines). Mainnet transactions are signed locally and submitted separately. Keys never enter GitHub — not in secrets, commits, logs, or artifacts.

**Testnet exception:** Testnet keys may be stored as GitHub Environment secrets (scoped to the `testnet` environment with required reviewers), because their compromise has limited impact and can be resolved by rotation.

Specific rules:

1. No cryptographic signing keys for mainnet in any GitHub-accessible location.
2. Deployments to mainnet use `workflow_dispatch` with environment gating — CI prepares artifacts, operator signs locally.
3. Testnet deployments may use GitHub Environment secrets for signing.
4. CI logs are treated as potentially public — no secret material may appear in output.
5. All key management follows `05_documentation/security/KEY_MANAGEMENT.md`.

## Consequences

- Mainnet deployments require an operator with physical access to signing hardware. This is intentional friction.
- CI can fully automate testnet deployments but not mainnet. Mainnet requires a manual signing step.
- Secrets never appear in repository history, reducing blast radius of any repository-level compromise.
- `workflow_dispatch` with environment gating provides auditability for who triggered deployments and when.
- Key rotation for testnet is a GitHub settings change. Key rotation for mainnet is a hardware procedure documented in `KEY_MANAGEMENT.md`.
- This model scales to multi-chain deployment by adding environments per chain while maintaining the same plane separation.

## Alternatives Rejected

### Keys in CI

Storing all keys (including mainnet) as GitHub secrets. Rejected because:

- GitHub secrets are accessible to any workflow in the environment; a compromised workflow can exfiltrate them.
- Secret values appear in memory during CI runs and could leak via debug logging or runner compromise.
- No hardware-backed protection for key material.

### Browser-Only Execution as Source of Truth

Using browser-based tools (e.g., Remix, wallet UIs) as the primary deployment mechanism, with the repository serving only as source storage. Rejected because:

- No reproducible build pipeline — deployments depend on operator's local browser environment.
- No CI gating — code can be deployed without passing tests or stability checks.
- No audit trail — browser-based actions are not captured in repository history.
- Contradicts PR-only merge policy and ROOT-24-LOCK governance model.

## References

- `05_documentation/security/THREATMODEL.md`
- `05_documentation/security/KEY_MANAGEMENT.md`
- `05_documentation/security/INCIDENT_RESPONSE.md`
