# SSID Phase 0 — Canonical Freeze & Source-of-Truth Lock

## Metadata
- package_id: SSID-PHASE0-20260326
- generated_at_utc: 2026-03-26T19:13:43Z
- status: READY_FOR_EXECUTION
- phase: 0
- mode: EMS-first, local-first, deterministic
- scope: Canonical source lock, repo role lock, source-priority lock, freeze rules, no implementation changes

## Ziel
Phase 0 friert das Projekt **kanonisch** ein, bevor weitere Build- oder Refactor-Arbeit beginnt.
Ergebnis ist **kein Feature-Bau**, sondern ein bindender Rahmen für alle Folgephasen.

## Harte Ziele
1. Eine einzige kanonische SoT-Hierarchie festlegen
2. Repo-Rollen final sperren
3. Source-Priority final sperren
4. Alt-/Drift-/Legacy-Quellen auf Evidence-only setzen
5. Standards- und Regulatorik-Referenzen finalisieren
6. Gate-Kriterien definieren, die Phase 0 objektiv abschließen

## Phase-0-Output
- Canonical source matrix
- Repo role matrix
- Standards baseline
- Launch-relevante regulatorische baseline
- Freeze/override rules
- Evidence + registry stub
- EXECUTION MASTER-PROMPT

## Kanonische Entscheidungen
### A. Repo-Rollen
- SSID = privates Hauptrepo, kanonisches Produkt-/Protokollsystem
- SSID-EMS = kanonische Steuerungs-, Audit-, Runtime- und Verifikationsschicht
- SSID-open-core = öffentlicher, bereinigter Mirror aus dem privaten Hauptsystem
- SSID-docs = öffentliche Dokumentation und Integrationsdoku

### B. Architektur-Trennung
- `chart.yaml` beschreibt **WAS**
- `manifest.yaml` beschreibt **WIE**
- Contracts/Schemas vor Implementierung
- Keine Manifest-Erzeugung ohne reale Implementierung
- Keine Wiederherstellung alter, abweichender Strukturvarianten

### C. Nicht verhandelbare Leitplanken
- ROOT-24-LOCK
- SAFE-FIX
- NEU gewinnt; ALT nur Evidence
- no quarantine for structure/policy/depth issues
- hash-only / non-custodial
- provider-direct verification model
- EMS-first for verification and control

## Bindende Quellebenen
### Tier 0 — kanonische Primärquellen
1. `ssid_master_definition_corrected_v1.1.1.md`
2. `SSID_structure_level3_part1_MAX.md`
3. `SSID_structure_level3_part2_MAX.md`
4. `SSID_structure_level3_part3_MAX.md`
5. `SSID_structure_gebühren_abo_modelle.md`
6. `SSID_structure_gebühren_abo_modelle_ROOTS_16_21_ADDENDUM.md`

### Tier 1 — bindende Schutz-/Release-/Mirror-Kontextquellen
7. `Ssid Protection Report.pdf`
8. `SSID_Maximalstand_Bericht_20250914_162116.pdf`
9. `SSID_OpenCore_Maximalstand_Bericht.pdf`

### Tier 2 — Kontext-/Strategiequellen
10. `Technische Grundlagen von SSI.pdf`
11. `Technische Grundlagen von SSI-2.pdf`
12. `Embedding a Permissionless SSID Token_ Applications Value Maximization.pdf`

### Tier 3 — Risiko-/Abgrenzungsquellen
13. `Überblick über SSID und das SSID-Token.pdf`
14. weitere historische/sekundäre Reports = reference only, niemals SoT

## Was Phase 0 explizit NICHT tut
- keine Kernlogik umbauen
- keine Contracts deployen
- keine Module implementieren
- keine Public-Mirror-Synchronisation starten
- keine Mainnet-Aktivität
- keine Struktur-Rückrestauration historischer Varianten

## Deliverables innerhalb des Zielrepos
1. `05_documentation/phase0/PHASE0_CANONICAL_SOURCE_MATRIX.md`
2. `05_documentation/phase0/PHASE0_REPO_ROLE_MATRIX.md`
3. `05_documentation/phase0/PHASE0_STANDARDS_BASELINE.md`
4. `05_documentation/phase0/PHASE0_REGULATORY_BASELINE.md`
5. `24_meta_orchestration/registry/phase0_registry_lock.json`
6. `23_compliance/evidence/phase0/phase0_canonical_freeze_report.json`
7. `23_compliance/evidence/phase0/phase0_source_hashes.json`
8. `23_compliance/evidence/phase0/phase0_decision_log.jsonl`
9. `17_observability/score/phase0_status.json`

## Abhängigkeiten für Phase 1
Phase 1 darf erst starten, wenn:
- alle Tier-0-Quellen gehasht und gelockt sind
- Source-Priority dokumentiert ist
- Repo-Rollen dokumentiert sind
- Standards-Baseline dokumentiert ist
- Regulatory-Baseline dokumentiert ist
- Freeze-Report PASS ist
- Drift-Liste abgearbeitet oder als Evidence klassifiziert ist

## Exit-Kriterien
- 1 kanonische SoT-Hierarchie
- 1 Repo-Rollenmatrix
- 1 Standards-/Regulatory-Baseline
- 1 Registry-Lock-Artefakt
- 1 Evidence-Paket mit Hashes
- 0 ungeklärte konkurrierende Quellen
- 0 ungeklärte Repo-Rollen
