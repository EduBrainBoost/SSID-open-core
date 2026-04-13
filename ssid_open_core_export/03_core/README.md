# 03_core — Core Validators & Authority

**Classification:** Internal Authority
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Final authority module for the SSID platform. Houses the master SoT validator,
security primitives (data minimization, forensic management), and the central
interface bus that all advisory modules route through.

## Structure

| Directory   | Purpose                                    |
|-------------|--------------------------------------------|
| `docs/`     | Module-level documentation                 |
| `src/`      | Core source code                           |
| `tests/`    | Module-scoped test stubs                   |
| `config/`   | Module configuration                       |
| `interfaces/` | Central bus definitions (ai_validator_bus) |
| `security/` | Data minimization, forensic manager        |
| `validators/` | SoT validator core                       |
| `shards/`   | 16 domain shards                           |

## Governance

- **SOT_AGENT_012**: Structure conforms to MUST paths
- **SOT_AGENT_013**: No shadow files or forbidden copies
- **SOT_AGENT_014**: Interfaces reference central paths

## Interfaces

- Output logs: `17_observability/logs/core/`
- Evidence target: `23_compliance/evidence/core/`
