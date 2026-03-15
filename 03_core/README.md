# 03_core — Core Validators & Authority

**Classification:** Internal Authority
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Central validation authority and final arbiter for all SSID module interactions. Delegates from 01_ai_layer.

## Structure

| Directory    | Purpose                              |
|-------------|--------------------------------------|
| `validators/` | SoT and structure validators        |
| `docs/`      | Module-level documentation           |
| `src/`       | Source code                          |
| `tests/`     | Module-scoped test stubs             |
| `config/`    | Module configuration                 |

## Governance

- **SOT_AGENT_012**: Structure conforms to MUST paths
- **SOT_AGENT_013**: No shadow files or forbidden copies
- **SOT_AGENT_014**: Interfaces reference central paths

## Interfaces

- Output logs: `17_observability/logs/core/`
- Evidence target: `23_compliance/evidence/core/`
