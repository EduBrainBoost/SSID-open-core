# 16_codex — Codex & Contracts

**Classification:** Governance
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Central governance codex containing architectural decision records (ADRs), SoT contracts, and binding governance rules for the SSID system.

## Structure

| Directory     | Purpose                              |
|--------------|--------------------------------------|
| `decisions/`  | Architectural Decision Records       |
| `contracts/`  | SoT contracts and binding rules      |
| `docs/`       | Module-level documentation           |
| `tests/`      | Module-scoped test stubs             |
| `config/`     | Module configuration                 |

## Governance

- **SOT_AGENT_021**: Structure conforms to MUST paths
- **SOT_AGENT_022**: No shadow files or forbidden copies
- **SOT_AGENT_023**: Interfaces reference central paths

## Interfaces

- Output logs: `17_observability/logs/codex/`
- Evidence target: `23_compliance/evidence/codex/`
