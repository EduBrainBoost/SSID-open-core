# 23_compliance — Compliance, Governance & Regulatory Framework

**Classification:** Compliance — Central Policy Authority
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Central compliance and regulatory governance hub for the SSID platform. Houses all
compliance policies, regulatory framework mappings (GDPR, eIDAS2, MiCA, NIS2, DORA,
AI Act, PSD2/PSD3), evidence collection targets, exception management, security
configurations, and audit cycle definitions. This is the single authoritative source
for all compliance-related artifacts. Final authority resides with `03_core`.

This module does NOT:
- Store customer PII (evidence is hash-only)
- Execute business logic (policy definitions only)
- Hold secrets or credentials

## Structure

| Directory                  | Purpose                                              |
|---------------------------|------------------------------------------------------|
| `docs/`                   | Compliance documentation                              |
| `src/`                    | Compliance tooling source code                        |
| `tests/`                  | Module-scoped tests                                   |
| `config/`                 | Compliance configuration                              |
| `policies/`               | Central compliance policies (referenced by all roots) |
| `evidence/`               | Evidence collection targets (per-root subdirectories) |
| `exceptions/`             | Root-level and structure exception definitions         |
| `frameworks/`             | Regulatory framework specifications                   |
| `mappings/`               | Regulatory mapping index (eIDAS2, GDPR, MiCA etc)    |
| `jurisdictions/`          | Jurisdiction-specific compliance rules                |
| `certificates/`           | Compliance certificates and attestations              |
| `badges/`                 | Compliance badge definitions                          |
| `governance/`             | Governance rules and enforcement                      |
| `rules/`                  | Compliance rule definitions                           |
| `validators/`             | Compliance validators                                 |
| `metrics/`                | Compliance metrics and KPIs                           |
| `security/`               | Security compliance configurations                    |
| `privacy/`                | Privacy compliance (GDPR, data minimization)          |
| `anti_gaming/`            | Anti-gaming and fraud prevention rules                |
| `ai_ml_ready/`            | AI/ML readiness compliance                            |
| `enterprise_adoption/`    | Enterprise adoption compliance requirements           |
| `social_ecosystem/`       | Social ecosystem compliance                           |
| `market_entry/`           | Market entry compliance requirements                  |
| `regulatory_intelligence/`| Regulatory intelligence tracking                      |
| `sector_audits/`          | Sector-specific audit configurations                  |
| `shards/`                 | 16 domain shards                                      |

## Key Files

- `compliance_matrix_global.yaml` — Global compliance matrix
- `audit_cycle.yaml` — Audit cycle and cadence definitions
- `fee_allocation_policy.yaml` — Fee allocation compliance policy
- `gitleaks.toml` — Secret scanning configuration

## Regulatory Frameworks

- GDPR (General Data Protection Regulation)
- eIDAS2 (Electronic Identification)
- MiCA (Markets in Crypto-Assets)
- NIS2 (Network and Information Security)
- DORA (Digital Operational Resilience Act)
- EU AI Act
- PSD2/PSD3 (Payment Services Directive)

## Interfaces

| Direction | Central Path | Description |
|-----------|-------------|-------------|
| Input | `23_compliance/evidence/*/` | Evidence from all modules |
| Output | `17_observability/logs/compliance/` | Log output specification |

## Governance

- **SOT_AGENT_060**: Structure conforms to MUST paths
- **SOT_AGENT_061**: No shadow files or forbidden copies
- **SOT_AGENT_062**: Interfaces reference central paths
