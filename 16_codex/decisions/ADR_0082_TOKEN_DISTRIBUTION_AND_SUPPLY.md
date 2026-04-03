# ADR-0082 — Kanonische Token-Distribution und Fixed-Supply-Modell

| Feld | Wert |
|------|------|
| ID | ADR-0082 |
| Status | ACCEPTED |
| Datum | 2026-03-31 |
| Autoren | SSID Architect |
| Entscheidungsebene | Governance / Tokenomics |
| Vorgänger-RFCs | RFC-TOKEN-DIST, RFC-INFLATION |
| Enforcement | ROOT-24-LOCK, SAFE-FIX |

---

## Kontext

Die kanonische Tokenomics-Spezifikation in `16_codex/SSID_structure_level3_part1_MAX.md` (SoT) definiert Token-Distribution und Inflation-Modell. Im Laufe der Implementierung sind in mehreren Dateien abweichende Werte entstanden (Implementation Drift), die nie durch einen formalen Governance-Prozess freigegeben wurden.

Der Konflikt wurde im Reality Audit (2026-03-30) aufgedeckt und ist in `02_audit_logging/reports/T010_TOKENOMICS_ALIGNMENT_MATRIX.json` dokumentiert.

---

## Entscheidung

### Kanonische Werte (SoT gewinnt)

#### TOKEN_DISTRIBUTION (Initiale Supply-Allokation)

| Kategorie | Kanonisch (SoT) | Drift-Wert | Quelle SoT |
|-----------|----------------|-----------|-----------|
| ecosystem_development | **40%** (400M SSID) | 30% | `16_codex/SSID_structure_level3_part1_MAX.md:155` |
| community_rewards | **25%** (250M SSID) | 25% | `16_codex/SSID_structure_level3_part1_MAX.md:156` |
| foundation_reserve | **15%** (150M SSID) | 20% | SoT implied |
| early_contributors | **10%** (100M SSID) | 15% | SoT implied |
| public_allocation | **10%** (100M SSID) | 10% | SoT implied |
| **Gesamt** | **100%** | 100% | |

#### INFLATION_MODEL

| Parameter | Kanonisch (SoT) | Drift-Wert | Quelle SoT |
|-----------|----------------|-----------|-----------|
| Inflation | **0% — Fixed Supply** | "2% annual" + halving alle 4 Jahre | `16_codex/SSID_structure_level3_part1_MAX.md:166` |
| Emission | **Keine Neu-Emission** | `annual_emission_rate: "2%"` | — |
| Halving | **Nicht anwendbar** | `emission_halving_interval_years: 4` | — |
| Supply-Mechanismus | **Deposit/Distribution-basiert** | Inflation-basiert | — |

---

## Begründung

### 1. SoT-Priorität

Für SSID gilt: **SoT ist kanonisch.** Code-Implementierungen ohne formale Governance-Freigabe sind Implementation Drift, keine Spezifikationsänderung. Zwei RFC-Instanzen (RFC-TOKEN-DIST, RFC-INFLATION) wurden ohne ADR-Entscheid im Code etabliert — dies wird hiermit formal korrigiert.

### 2. Reward-Modell ist deposit-basiert

Die aktuelle Reward-Spezifikation beschreibt `deposited_rewards` und Claims gegen vorhandene Bestände. Die Fee-Spezifikation ist auf deterministische Splits und Ledger-Verteilung ausgelegt. Beide sind strukturell inkompatibel mit inflationärer Mint-Logik.

### 3. Regulatorische Sauberkeit

Ein Fixed-Supply-Modell mit utility/governance/reward without payment obligation ist für SSID regulatorisch und architektonisch klarer als ein Emissions-/Halving-Modell. Inflation erzeugt unnötige Governance-, Bewertungs- und Angriffsfläche.

### 4. Konsistenz mit bestehenden Mechanismen

Das Burn-Modell (`system_treasury_percent: 2.0`, `burn_from_treasury_percent: 50`) ist bereits deflationary — also entgegengesetzt zu Inflation. Beides gleichzeitig ist widersprüchlich.

---

## Scope-Abgrenzung: Token-Distribution vs. Fee-Splits

Diese ADR betrifft **ausschließlich die initiale Token Supply-Allokation** (40/25/15/10/10) und das **Inflation-Modell** (0% Fixed Supply).

**Nicht betroffen** von dieser ADR:
- Transaktionsgebühren-Splits in `fee_distribution_engine.py` (0.30 PLATFORM/CREATOR/OPERATOR) — diese betreffen die Verteilung von *Gebühreneinnahmen*, nicht die Token-Supply-Allokation. Sie folgen einer separaten Governance-Linie (`fee_allocation_policy.yaml`).
- Burn-Mechanismus (`system_treasury_percent: 2.0`) — dieser bleibt unverändert und ist mit Fixed Supply kompatibel (burn reduziert Supply, keine Neu-Emission).

---

## Konsequenzen

### Sofort (READ-ONLY, keine Code-Änderung ohne explizite APPLY-Freigabe)

Alle abweichenden Implementierungen sind **Implementation Drift** und müssen remediert werden. Siehe `GOVERNANCE_DRIFT_REPORT.md` und `GOVERNANCE_REMEDIATION_PLAN.md`.

### Nach APPLY-Freigabe (separater PR pro Datei)

1. `20_foundation/tokenomics/token_economics.yaml` — distribution: 30→40, 20→15; inflation: "2%"→"0%"; halving entfernen
2. `20_foundation/tokenomics/ssid_token_framework.yaml` — inflation_model: "deflationary_cap"→"fixed_supply"
3. `20_foundation/tokenomics/ssid_token_sink_model.yaml` — Inflation-Referenz entfernen
4. Tests und Schemas: SoT-Werte als einzige Erwartung festschreiben

### Unveränderlich (kein Remediation erforderlich)

- `fee_distribution_engine.py` 0.30-Splits (Fee-Modell, nicht Token-Distribution)
- `LicenseFeeRouter.sol` burn/treasury-Mechanismus (kompatibel mit Fixed Supply)
- `SSIDTokenFee.sol` TOTAL_SUPPLY-Konstante (korrekt, keine Inflation im Contract)

---

## Referenzen

- SoT: `16_codex/SSID_structure_level3_part1_MAX.md:155-166`
- Drift-Dokumentation: `16_codex/decisions/GOVERNANCE_DRIFT_REPORT.md`
- Remediation: `16_codex/decisions/GOVERNANCE_REMEDIATION_PLAN.md`
- Reality Audit: `02_audit_logging/reports/T010_TOKENOMICS_ALIGNMENT_MATRIX.json`
- Vorgänger: ADR-0071 (SSIDToken Permit vs Fee)
