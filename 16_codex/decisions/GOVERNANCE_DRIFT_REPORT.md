# GOVERNANCE DRIFT REPORT — Token Distribution & Supply Model

| Feld | Wert |
|------|------|
| Erstellt | 2026-03-31T000000Z |
| ADR-Referenz | ADR-0082 |
| Status | AUDIT_COMPLETE — REMEDIATION_PENDING |
| Scope | TOKEN_DISTRIBUTION, INFLATION_MODEL |

---

## Kanonische Werte (SoT)

| Parameter | Kanonischer Wert | Quelle |
|-----------|----------------|--------|
| ecosystem_development | 40% | `16_codex/SSID_structure_level3_part1_MAX.md:155` |
| community_rewards | 25% | `16_codex/SSID_structure_level3_part1_MAX.md:156` |
| foundation_reserve | 15% | SoT v4.1 |
| early_contributors | 10% | SoT v4.1 |
| public_allocation | 10% | SoT v4.1 |
| inflation_model | 0% Fixed Supply | `16_codex/SSID_structure_level3_part1_MAX.md:166` |
| annual_emission_rate | none | — |
| halving | none | — |

---

## Drift-Funde

### DRIFT-001 — token_economics.yaml: Distribution 30/25/20/15/10

| Feld | Wert |
|------|------|
| Datei | `20_foundation/tokenomics/token_economics.yaml` |
| Zeilen | 18–46 |
| Typ | TOKEN_DISTRIBUTION |
| Drift-Wert | ecosystem_development=30%, community_rewards=25%, foundation_reserve=20%, early_contributors=15%, public_allocation=10% |
| Kanonisch | 40/25/15/10/10 |
| Schwere | CRITICAL — primäre Tokenomics-Definition |
| Remediation | Pflicht, separater PR |

### DRIFT-002 — token_economics.yaml: Inflation 2% + Halving

| Feld | Wert |
|------|------|
| Datei | `20_foundation/tokenomics/token_economics.yaml` |
| Zeilen | 13–15 |
| Typ | INFLATION_MODEL |
| Drift-Wert | `inflation_model: "deflationary_cap"`, `annual_emission_rate: "2%"`, `emission_halving_interval_years: 4` |
| Kanonisch | `inflation_model: "fixed_supply"`, keine Emission, kein Halving |
| Schwere | CRITICAL — direkt widersprüchlich zum Fixed-Supply-Modell |
| Remediation | Pflicht, separater PR |

### DRIFT-003 — ssid_token_framework.yaml: inflation_model falsch

| Feld | Wert |
|------|------|
| Datei | `20_foundation/tokenomics/ssid_token_framework.yaml` |
| Zeile | 54 |
| Typ | INFLATION_MODEL |
| Drift-Wert | `inflation_model: "deflationary_cap"` |
| Kanonisch | `inflation_model: "fixed_supply"` |
| Schwere | MEDIUM — inkonsistente Terminologie, falsche Modellklassifikation |
| Anmerkung | "deflationary_cap" ist nicht falsch in der Wirkung (Burn → deflationär), aber die Klassifikation suggeriert Emission + Reduktion statt Fixed Supply + Burn |
| Remediation | Pflicht, separater PR |

### DRIFT-004 — ssid_token_sink_model.yaml: Implizite 2%-Inflation-Referenz

| Feld | Wert |
|------|------|
| Datei | `20_foundation/tokenomics/ssid_token_sink_model.yaml` |
| Zeile | 6 |
| Typ | INFLATION_MODEL |
| Drift-Wert | `rate_bps: 100  # 1% = 50% of 2% system treasury, burned` |
| Kanonisch | Kommentar muss entfernt werden; `rate_bps: 100` (1% Burn) bleibt korrekt — der Burn-Mechanismus ist unabhängig vom Supply-Modell |
| Schwere | LOW — Kommentar-Drift, kein Logik-Fehler |
| Remediation | Kommentar korrigieren, Logik bleibt |

---

## Nicht-Drift (zur Klarstellung)

Die folgenden 0.30-Werte sind **KEIN Drift** — sie betreffen Transaktionsgebühren-Splits (Fee-Modell), nicht Token-Supply-Allokation:

| Datei | Zeilen | Wert | Klassifikation |
|-------|--------|------|----------------|
| `03_core/fee_distribution_engine.py` | 104, 117, 127 | `Decimal("0.30")` (PLATFORM/CREATOR/OPERATOR) | FEE_MODEL — kein Token-Distribution-Drift |
| `03_core/interfaces/json_schemas/fee_distribution.schema.json` | 86, 180 | `"provider": 0.30` | FEE_MODEL — Schema-Beispielwert |
| `03_core/license_fee_splitter.py` | 130 | `platform=0.30, creator=0.45` | FEE_MODEL — Lizenzgebühren-Split |
| `07_governance_legal/subscription_revenue_policy.yaml` | 17 | `percent: 30` | SUBSCRIPTION_REVENUE — DAO-Treasury-Anteil an Abos |
| `07_governance_legal/docs/pricing/enterprise_subscription_model_v5.1.yaml` | 370–378 | `0.30`, `dao_treasury_percent: 30` | PRICING — Preismodell-Konfiguration |

Diese Werte erfordern eine **separate Governance-Entscheidung** (Fee-Modell ADR), die nicht Teil dieser ADR ist.

---

## Übersicht: Remediation-Dringlichkeit

| ID | Datei | Schwere | Action |
|----|-------|---------|--------|
| DRIFT-001 | `20_foundation/tokenomics/token_economics.yaml` | CRITICAL | PR erforderlich |
| DRIFT-002 | `20_foundation/tokenomics/token_economics.yaml` | CRITICAL | PR erforderlich |
| DRIFT-003 | `20_foundation/tokenomics/ssid_token_framework.yaml` | MEDIUM | PR erforderlich |
| DRIFT-004 | `20_foundation/tokenomics/ssid_token_sink_model.yaml` | LOW | Kommentar-Fix im selben PR wie DRIFT-003 |
