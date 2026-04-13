# ADR-0057: Supply-Chain SBOM Export

- **Status:** Accepted
- **Date (UTC):** 2026-03-03
- **Scope:** `12_tooling/supply_chain/`

## Context

SSID requires a deterministic Software Bill of Materials (SBOM) for supply-chain transparency.
Changes under `12_tooling/` trigger the repo separation guard (ADR required).

## Decision

Add `12_tooling/supply_chain/sbom_export.py`:
- Priority lockfile detection (requirements.lock > poetry.lock > pdm.lock > pip freeze)
- Deterministic output: sorted packages, stable schema v1.0, SHA-256 of input source
- Secret-pattern guard: 7 auditable deny patterns (AWS, GitHub, PEM, OpenAI, Slack, Google, GitLab)
- CI workflow (`.github/workflows/supply_chain.yml`) produces artifact (sbom.json + .sha256)
- No repo write: evidence only via CI artifact upload or external local path

## Consequences

- Guard passes (ADR present for the triggered prefix).
- Supply-chain SBOM is reproducible and auditable.
- Secret leakage in SBOM output is prevented by deny-pattern check.
