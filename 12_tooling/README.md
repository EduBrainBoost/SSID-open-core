# 12_tooling — Developer Tooling & CLI Infrastructure

**Classification:** Developer Tools
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Developer tooling, CLI utilities, and operational infrastructure for the SSID platform.
Houses the SoT validator CLI, security scanning tools, SBOM generation, supply chain
verification, schema validators, and the SSID autorunner. Provides the operational
backbone that enforces structural and governance rules across all modules.
Final authority resides with `03_core`.

This module does NOT:
- Store or process customer PII
- Define compliance policies (those reside in `23_compliance/`)
- Hold production secrets

## Not Maintained Here

| Domain | Central Location |
|--------|-----------------|
| Compliance policies | `23_compliance/policies/` |
| Security baselines | `23_compliance/` |
| Global registry | `24_meta_orchestration/registry/` |

## Structure

| Directory          | Purpose                                         |
|--------------------|------------------------------------------------|
| `docs/`            | Module-level documentation                      |
| `src/`             | Tooling source code                             |
| `tests/`           | Module-scoped tests                             |
| `config/`          | Tool configuration                              |
| `cli/`             | Command-line interface tools (sot_validator etc) |
| `hooks/`           | Git hooks and CI hooks                          |
| `ops/`             | Operational utilities                           |
| `sbom/`            | Software Bill of Materials generation           |
| `schemas/`         | Schema validation definitions                   |
| `scripts/`         | Automation scripts                              |
| `security/`        | Security scanning tools                         |
| `supply_chain/`    | Supply chain verification                       |
| `ssid_autorunner/` | Automated test/build runner                     |
| `policies/`        | Module-internal tooling policies                |
| `shards/`          | 16 domain shards                                |

## Key Tools

- `cli/sot_validator.py` — SoT structure validator (used by all roots)
- `ssid_autorunner/` — Automated CI/test execution framework
- `sbom/` — SBOM generation and verification
- `supply_chain/` — Dependency verification and attestation

## Interfaces

| Direction | Central Path | Description |
|-----------|-------------|-------------|
| Output | `17_observability/logs/tooling/` | Log output specification |
| Output | `23_compliance/evidence/tooling/` | Evidence path (hash-only) |

## Governance

- **SOT_AGENT_030**: Structure conforms to MUST paths
- **SOT_AGENT_031**: No shadow files or forbidden copies
- **SOT_AGENT_032**: Interfaces reference central paths
