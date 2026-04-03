# GOVERNANCE REMEDIATION PLAN — Token Distribution & Supply Model

| Feld | Wert |
|------|------|
| Erstellt | 2026-03-31T000000Z |
| ADR-Referenz | ADR-0082 |
| Status | PLAN — APPROVAL_REQUIRED vor APPLY |
| Blöcke | 2 PRs |

---

## Vorbedingungen

- ADR-0082 ist ACCEPTED (hiermit erfüllt)
- GOVERNANCE_DRIFT_REPORT.md dokumentiert alle Abweichungen
- SAFE-FIX: SHA256 before/after je Datei
- ROOT-24-LOCK: alle Änderungen in erlaubten Roots
- Keine Kernlogik-Änderung ohne explizite APPLY-Freigabe

---

## PR 1 — `fix(tokenomics): token_economics.yaml auf SoT-Werte normalisieren`

**Branch:** `fix/governance-token-economics-sot-alignment`
**Dateien:** 1

### Änderung

Datei: `20_foundation/tokenomics/token_economics.yaml`

```yaml
# VORHER (Drift)
distribution:
  - category: "ecosystem_development"
    percentage: 30          # ← DRIFT: muss 40
  - category: "community_rewards"
    percentage: 25          # ← OK
  - category: "foundation_reserve"
    percentage: 20          # ← DRIFT: muss 15
  - category: "early_contributors"
    percentage: 15          # ← DRIFT: muss 10
  - category: "public_allocation"
    percentage: 10          # ← OK

supply:
  inflation_model: "deflationary_cap"     # ← DRIFT: muss "fixed_supply"
  annual_emission_rate: "2%"              # ← DRIFT: entfernen
  emission_halving_interval_years: 4      # ← DRIFT: entfernen

# NACHHER (SoT)
distribution:
  - category: "ecosystem_development"
    percentage: 40          # SoT: 400M SSID
  - category: "community_rewards"
    percentage: 25          # SoT: 250M SSID
  - category: "foundation_reserve"
    percentage: 15          # SoT: 150M SSID
  - category: "early_contributors"
    percentage: 10          # SoT: 100M SSID
  - category: "public_allocation"
    percentage: 10          # SoT: 100M SSID

supply:
  inflation_model: "fixed_supply"         # ADR-0082
  # annual_emission_rate: entfernt        # ADR-0082: Fixed Supply, keine Emission
  # emission_halving_interval_years:      # ADR-0082: nicht anwendbar
```

**SHA256 erforderlich:** before + after `token_economics.yaml`

---

## PR 2 — `fix(tokenomics): ssid_token_framework und sink_model auf Fixed Supply normalisieren`

**Branch:** `fix/governance-token-framework-fixed-supply`
**Dateien:** 2

### Änderung 2a

Datei: `20_foundation/tokenomics/ssid_token_framework.yaml:54`

```yaml
# VORHER (Drift)
inflation_model: "deflationary_cap"

# NACHHER (ADR-0082)
inflation_model: "fixed_supply"  # ADR-0082: 0% Fixed Supply, kein Halving
```

### Änderung 2b

Datei: `20_foundation/tokenomics/ssid_token_sink_model.yaml:6`

```yaml
# VORHER (Kommentar-Drift)
rate_bps: 100  # 1% = 50% of 2% system treasury, burned

# NACHHER (Kommentar-Fix, Logik bleibt)
rate_bps: 100  # 1% effective burn rate (fee model: 2% treasury × 50% burn)
               # Note: burn is independent of supply model (ADR-0082: Fixed Supply)
```

**SHA256 erforderlich:** before + after je Datei (2 Einträge)

---

## Test-Anpassungen (nach PR 1+2, separater PR)

Dateien die nach Code-Änderung ggf. aktualisiert werden müssen:

| Datei | Anpassung |
|-------|-----------|
| `03_core/tests/test_fee_distribution_engine.py` | Wenn distribution-Werte in Assertions verwendet: auf 40/25/15/10/10 setzen |
| `11_test_simulation/tests/test_phase5_components.py` | Prüfen ob Token-Distribution-Assertions vorhanden |

**Erst nach APPLY-Freigabe der PRs 1+2.**

---

## Was NICHT geändert wird (explizit ausgeschlossen)

| Datei | Grund |
|-------|-------|
| `03_core/fee_distribution_engine.py` | Fee-Modell, nicht Token-Distribution — eigene Governance |
| `03_core/interfaces/json_schemas/fee_distribution.schema.json` | Fee-Schema |
| `03_core/license_fee_splitter.py` | Lizenzgebühren-Split |
| `20_foundation/hardhat/contracts/governance/SSIDTokenFee.sol` | Nur TOTAL_SUPPLY und Fee-Mechanismus — kein Token-Distribution-Drift |
| `20_foundation/tokenomics/contracts/RewardTreasury.sol` | Deposit/Distribution-Logik korrekt |
| `07_governance_legal/subscription_revenue_policy.yaml` | Subscription-Revenue, eigene Governance |

---

## Erfolgskriterium

- `token_economics.yaml` distribution summiert zu 100% mit Werten 40/25/15/10/10
- `inflation_model: "fixed_supply"` in allen drei Tokenomics-Dateien konsistent
- Kein `annual_emission_rate` oder `emission_halving_interval_years` in kanonischen Dateien
- SHA256-Manifest vor/nach je PR erstellt
- Tests grün

---

## Freigabe-Status

| PR | Status |
|----|--------|
| PR 1 (token_economics.yaml) | PLAN — APPROVAL_REQUIRED |
| PR 2 (framework + sink_model) | PLAN — APPROVAL_REQUIRED |
| Test-Anpassungen | PLAN — nach PR 1+2 |
