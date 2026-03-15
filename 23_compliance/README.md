# 23_compliance — Compliance & Governance

**Classification:** Compliance
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Regulatory compliance enforcement including OPA policies, exception allowlists, and evidence tracking for the SSID system.

## Structure

| Directory      | Purpose                              |
|---------------|--------------------------------------|
| `policies/`    | OPA .rego policy files               |
| `exceptions/`  | Root-level exception allowlists      |
| `evidence/`    | Compliance evidence targets          |
| `docs/`        | Module-level documentation           |
| `tests/`       | Module-scoped test stubs             |
| `config/`      | Module configuration                 |

## Governance

- **SOT_AGENT_021**: Structure conforms to MUST paths
- **SOT_AGENT_022**: No shadow files or forbidden copies
- **SOT_AGENT_023**: Interfaces reference central paths

## Interfaces

- Output logs: `17_observability/logs/compliance/`
- Evidence target: `23_compliance/evidence/compliance/`
