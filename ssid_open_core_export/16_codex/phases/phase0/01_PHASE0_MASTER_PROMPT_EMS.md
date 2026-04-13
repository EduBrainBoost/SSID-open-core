Voraussetzungen:
- SAFE-FIX und ROOT-24-LOCK sind strikt enforced
- Pfade:
  - SSID: ~/Documents/Github/SSID
- Der SSID-Parser liest ausschließlich lokal gespeicherte Regeln. Keine live-MD-Dateien, die MD ist nicht mehr SOT (Single Source of Truth).
- Der Dispatcher `dispatcher.py` ist aktiv (Blueprint 4.1, NON-INTERACTIVE, SAFE-FIX, ROOT-24-LOCK, SHA256-geloggt, keine Platzhalter, etc.).

SSID PHASE 0 — CANONICAL FREEZE / SOURCE-OF-TRUTH LOCK

Arbeitsmodus:
- Local-first
- Read/analyze/write only inside assigned worktree
- Kein Branch-Wechsel außerhalb des zugewiesenen Scopes
- Kein Public Push
- Keine Kernlogikänderung
- Keine Manifest-Erzeugung ohne reale Implementierung
- Kein Restore historischer Alternativstrukturen
- NEU gewinnt, ALT nur Evidence
- Alles deterministisch, auditierbar, fail-closed

Ziel:
Führe ausschließlich Phase 0 aus. Phase 0 bedeutet:
1. kanonische SoT-Hierarchie finalisieren
2. Repo-Rollen finalisieren
3. Source-Priority finalisieren
4. Standards- und Regulatory-Baseline finalisieren
5. Freeze-/Evidence-/Registry-Artefakte erzeugen
6. Phase-1-Startbedingungen objektiv definieren

Kanonische Priorität:
Tier 0 — einzige SoT:
- ssid_master_definition_corrected_v1.1.1.md
- SSID_structure_level3_part1_MAX.md
- SSID_structure_level3_part2_MAX.md
- SSID_structure_level3_part3_MAX.md
- SSID_structure_gebühren_abo_modelle.md
- SSID_structure_gebühren_abo_modelle_ROOTS_16_21_ADDENDUM.md

Tier 1 — bindender Betriebs-/Release-Kontext:
- Ssid Protection Report.pdf
- SSID_Maximalstand_Bericht_20250914_162116.pdf
- SSID_OpenCore_Maximalstand_Bericht.pdf

Tier 2 — Strategie-/Rationalekontext:
- Technische Grundlagen von SSI.pdf
- Technische Grundlagen von SSI-2.pdf
- Embedding a Permissionless SSID Token_ Applications Value Maximization.pdf

Tier 3 — Risiko-/Abgrenzung:
- Überblick über SSID und das SSID-Token.pdf

Verbindliche Repo-Rollen:
- SSID = privates Hauptrepo, Produkt-/Protokoll-SoT
- SSID-EMS = zentrale Betriebs-, Audit-, Runtime- und Verifikationsschicht
- SSID-open-core = öffentlicher bereinigter Mirror
- SSID-docs = öffentliche Dokumentation

Verbindliche Architekturregeln:
- chart.yaml = WAS
- manifest.yaml = WIE
- Contracts/Schemas vor Implementierung
- 24 Roots fix
- 16 Shards pro Root
- no quarantine for structure/policy/depth
- hash-only / non-custodial
- provider-direct verification model
- EMS-first for control and verification

Externe Baseline, die in Phase 0 dokumentiert werden muss:
- W3C DID Core 1.0
- W3C Verifiable Credentials Data Model 2.0
- OpenID4VCI 1.0
- OpenID4VP 1.0
- EUDI Wallet / eIDAS-2 Framework
- MiCA
- EU AI Act

Erzeuge exakt diese Artefakte:
1. 05_documentation/phase0/PHASE0_CANONICAL_SOURCE_MATRIX.md
2. 05_documentation/phase0/PHASE0_REPO_ROLE_MATRIX.md
3. 05_documentation/phase0/PHASE0_STANDARDS_BASELINE.md
4. 05_documentation/phase0/PHASE0_REGULATORY_BASELINE.md
5. 24_meta_orchestration/registry/phase0_registry_lock.json
6. 23_compliance/evidence/phase0/phase0_canonical_freeze_report.json
7. 23_compliance/evidence/phase0/phase0_source_hashes.json
8. 23_compliance/evidence/phase0/phase0_decision_log.jsonl
9. 17_observability/score/phase0_status.json

Pflichtinhalt der Artefakte:
- UTC ISO8601 timestamps
- source hashes
- rationale
- decision owner
- evidence references
- next-phase blockers/unblockers
- PASS/FAIL status
- keine Fantasiepfade
- keine unbewiesenen Aussagen

Arbeitsreihenfolge:
A. Inventarisiere alle Phase-0-Quellen lokal
B. Berechne SHA256 je Quelle
C. Erzeuge die Source-Matrix
D. Erzeuge die Repo-Rollenmatrix
E. Erzeuge Standards-Baseline
F. Erzeuge Regulatory-Baseline
G. Erzeuge Registry-Lock + Evidence-Files
H. Bewerte Gate-Status
I. Liefere Abschlussreport

Abbruchkriterien:
- konkurrierende gleichrangige SoT
- unklare Repo-Rollen
- Root-24-LOCK-Verstoß
- Versuch, Kernlogik oder Mainnet zu verändern
- Versuch, OpenCore zu veröffentlichen
- Manifest-Erzeugung ohne reale Implementierung

Definition of Done:
- genau eine kanonische SoT-Hierarchie dokumentiert
- Repo-Rollen final dokumentiert
- Standards-/Regulatory-Baseline dokumentiert
- Registry-Lock erzeugt
- Evidence-Paket erzeugt
- Phase-0-Status objektiv PASS oder BLOCKED ausgewiesen
- Phase-1-Startbedingungen dokumentiert

Finaler Output:
- knapper Abschlussbericht
- Liste der erzeugten Dateien
- offene Blocker
- SHA256 der erzeugten Hauptartefakte
- klare Aussage: PHASE 0 PASS oder PHASE 0 BLOCKED
