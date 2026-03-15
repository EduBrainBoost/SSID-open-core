# 12_tooling — Tooling & CLI Infrastructure

**Classification:** Developer Tools
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Developer tooling, CLI infrastructure, gate scripts, and automation utilities for the SSID ecosystem.

## Structure

| Directory   | Purpose                              |
|-------------|--------------------------------------|
| `cli/`      | CLI tools and dispatchers            |
| `scripts/`  | Automation and gate scripts          |
| `security/` | Security scanning utilities          |
| `docs/`     | Module-level documentation           |
| `tests/`    | Module-scoped test stubs             |
| `config/`   | Module configuration                 |

## Governance

- **SOT_AGENT_021**: Structure conforms to MUST paths
- **SOT_AGENT_022**: No shadow files or forbidden copies
- **SOT_AGENT_023**: Interfaces reference central paths

## Interfaces

- Output logs: `17_observability/logs/tooling/`
- Evidence target: `23_compliance/evidence/tooling/`
