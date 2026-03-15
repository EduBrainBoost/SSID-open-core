# 24_meta_orchestration — Meta Orchestration

**Classification:** Orchestration
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Workflow orchestration layer including the E2E dispatcher, registry management, and cross-module coordination for the SSID system.

## Structure

| Directory      | Purpose                              |
|---------------|--------------------------------------|
| `dispatcher/`  | E2E dispatcher and pipeline engine   |
| `registry/`    | SoT registry and structure specs     |
| `docs/`        | Module-level documentation           |
| `tests/`       | Module-scoped test stubs             |
| `config/`      | Module configuration                 |

## Governance

- **SOT_AGENT_021**: Structure conforms to MUST paths
- **SOT_AGENT_022**: No shadow files or forbidden copies
- **SOT_AGENT_023**: Interfaces reference central paths

## Interfaces

- Output logs: `17_observability/logs/meta_orchestration/`
- Evidence target: `23_compliance/evidence/meta_orchestration/`
