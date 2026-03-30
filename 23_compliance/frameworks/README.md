# 23_compliance/frameworks — Regulatory Framework Compliance Mappings

**Classification:** Compliance
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK
**Generated:** 2026-03-15

## Overview

This directory contains compliance mapping files that map SSID platform
capabilities (roots and shards) to the requirements of major regulatory
frameworks. Each framework directory contains:

- A `*_mapping.yaml` — article-level or recommendation-level mapping of
  regulatory requirements to the SSID roots/shards that implement them.
- A `*_controls.yaml` — specific controls required by the regulation, with
  implementation ownership, supporting roots, shard scope, and evidence paths.

All mappings reference SSID roots as the unit of implementation. The
final authority for all compliance decisions is `03_core`.

---

## Frameworks

| Directory | Regulation | Jurisdiction | Effective |
|-----------|-----------|--------------|-----------|
| `gdpr/` | GDPR — General Data Protection Regulation (EU) 2016/679 | EU / EEA | 2018-05-25 |
| `eidas/` | eIDAS 2.0 — Electronic Identification and Trust Services (EU) 2024/1183 | EU / EEA | 2026-05-20 |
| `mica/` | MiCA — Markets in Crypto-Assets Regulation (EU) 2023/1114 | EU / EEA | 2024-12-30 |
| `amld6/` | AMLD6 — 6th Anti-Money Laundering Directive (EU) 2018/1673 | EU / EEA | 2020-12-03 |
| `fatf/` | FATF — 40 Recommendations (2012, updated 2023) | Global | Ongoing |
| `iso27001/` | ISO/IEC 27001 — Information Security Management System | Global | Ongoing |
| `soc2/` | SOC 2 Type II — Trust Service Criteria (AICPA) | Global | Ongoing |

---

## SSID Roots Referenced

The following SSID roots appear most frequently across framework mappings:

| Root | Name | Role |
|------|------|------|
| `03_core` | Core Validators & Authority | Final authority; gate enforcement |
| `02_audit_logging` | Audit Logging & Evidence | WORM records; retention; breach detection |
| `08_identity_score` | Identity Score & Reputation | KYC, risk scoring, PEP/sanctions screening |
| `09_meta_identity` | Meta-Identity | Composite identity; portability |
| `10_interoperability` | Interoperability Framework | Travel rule; cross-border; EUDIW protocols |
| `14_zero_time_auth` | Zero-Time Authentication | Secure access; wallet authentication |
| `21_post_quantum_crypto` | Post-Quantum Cryptography | Encryption; QES; cryptographic binding |
| `23_compliance` | Compliance & Governance | Policy registry; evidence targets |

---

## SSID Shards Referenced

The following shards within `23_compliance/shards/` carry the highest
compliance relevance across frameworks:

| Shard | Relevance |
|-------|-----------|
| `01_identitaet_personen` | Core identity — all frameworks |
| `02_dokumente_nachweise` | Document verification — GDPR, eIDAS, AMLD6, FATF |
| `05_gesundheit_medizin` | Health data — GDPR Art. 9, eIDAS EUDIW |
| `10_finanzen_banking` | Financial accounts — MiCA, AMLD6, FATF |
| `13_unternehmen_gewerbe` | Legal entities — MiCA, AMLD6, FATF UBO |
| `14_vertraege_vereinbarungen` | Contracts — GDPR, eIDAS QES |
| `15_handel_transaktionen` | Transactions — MiCA Travel Rule, FATF R.16 |
| `16_behoerden_verwaltung` | Public authority — eIDAS cross-border |

---

## Evidence Paths

Controls in this directory write evidence to:

```
23_compliance/evidence/gdpr/
23_compliance/evidence/eidas/
23_compliance/evidence/mica/
23_compliance/evidence/amld6/
23_compliance/evidence/fatf/
```

Evidence strategy: `hash_manifest_only` (no raw PII persisted).

---

## Governance

- Final authority: `03_core`
- Log sink: `17_observability/logs/compliance/`
- Governance rules: SOT_AGENT_021, SOT_AGENT_022, SOT_AGENT_023
