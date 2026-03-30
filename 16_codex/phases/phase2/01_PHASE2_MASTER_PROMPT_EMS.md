Voraussetzungen:
- SAFE-FIX und ROOT-24-LOCK sind strikt enforced
- Pfade:
  - SSID: ~/Documents/Github/SSID
- Der SSID-Parser liest ausschließlich lokal gespeicherte Regeln. Keine live-MD-Dateien, die MD ist nicht mehr SOT (Single Source of Truth).
- Der Dispatcher `dispatcher.py` ist aktiv (Blueprint 4.1, NON-INTERACTIVE, SAFE-FIX, ROOT-24-LOCK, SHA256-geloggt, keine Platzhalter, etc.).

SSID GLOBAL PHASE 2 — 384-SOT-COMPLETION

Arbeitsmodus:
- Local-first
- Ein Chat = ein Scope = ein Branch = ein Worktree
- Kein Branch-Wechsel außerhalb des zugewiesenen Scopes
- Kein Public Push
- Keine Kernlogikänderung
- Keine Manifest-Erzeugung ohne reale Implementierung
- Keine historischen Strukturen restaurieren
- NEU gewinnt, ALT nur Evidence
- Deterministisch, auditierbar, fail-closed

WICHTIGE KLARSTELLUNG:
- Diese Phase 2 ist die globale SSID-Roadmap-Phase „384 Chart Completion“
- NICHT die interne Kapitelphase aus der Master-Definition „Shard_01 implementieren“

Ziel:
1. Inventarisiere alle 24×16 = 384 Chart-Einheiten
2. Ermittle pro Chart den Status: MISSING / SCAFFOLD_ONLY / PARTIAL / POLICY_INCOMPLETE / GOVERNANCE_INCOMPLETE / EVIDENCE_INCOMPLETE / READY_FOR_REVIEW
3. Vereinheitliche die Chart-Mindeststruktur
4. Befülle oder normalisiere alle Charts auf SoT-Niveau
5. Führe Cross-root Konsistenzprüfung durch
6. Erzeuge Registry-, Evidence- und Status-Artefakte
7. Markiere nur reale Phase-3-Manifest-Kandidaten, aber erzeuge keine Manifest-Dateien

Verbindliche Quellen:
Tier 0:
- ssid_master_definition_corrected_v1.1.1.md
- SSID_structure_level3_part1_MAX.md
- SSID_structure_level3_part2_MAX.md
- SSID_structure_level3_part3_MAX.md
- SSID_structure_gebühren_abo_modelle.md
- SSID_structure_gebühren_abo_modelle_ROOTS_16_21_ADDENDUM.md

Tier 1:
- SSID_Maximalstand_Bericht_20250914_162116.pdf
- Ssid Protection Report.pdf
- SSID_OpenCore_Maximalstand_Bericht.pdf

Verbindliche Phase-2-Regeln:
- chart.yaml beschreibt nur WAS
- manifest.yaml beschreibt nur WIE
- Contract-first
- 384 Charts, keine Ausnahmen
- Non-custodial / hash-only
- Keine PII-Speicherung
- Evidence/WORM-geeignete Pfade
- Registry-Semantik gemäß Level-3
- Dual Review für Chart-Änderungen (Architecture + Compliance)
- Promotion-Regeln dokumentieren
- Observability und Testing schon auf Chart-Ebene beschreiben

Mindestinhalt jeder chart.yaml:
- metadata
- purpose
- capabilities
- interfaces
- policies
- compliance
- governance
- evidence
- observability
- testing
- implementation_handoff
- release

Arbeitswellen:
- Welle A: 16_codex, 24_meta_orchestration, 23_compliance, 02_audit_logging
- Welle B: 03_core, 19_adapters, 10_interoperability, 14_zero_time_auth
- Welle C: 20_foundation, 09_meta_identity, 17_observability, 15_infra
- Welle D: 01_ai_layer, 08_identity_score, 18_data_layer, 06_data_pipeline
- Welle E: 11_test_simulation, 12_tooling, 13_ui_layer, 05_documentation
- Welle F: 07_governance_legal, 21_post_quantum_crypto, 22_datasets, 04_deployment

Erzeuge exakt diese Artefakte:
1. 05_documentation/phase2/PHASE2_384_CHART_COMPLETION_PLAN.md
2. 05_documentation/phase2/PHASE2_ROOT_SHARD_STATUS_MATRIX.md
3. 05_documentation/phase2/PHASE2_CHART_TEMPLATE_SPEC.md
4. 24_meta_orchestration/registry/manifests/phase2_chart_completion_manifest.json
5. 24_meta_orchestration/registry/manifests/phase2_chart_gap_matrix.json
6. 23_compliance/evidence/phase2/phase2_chart_completion_audit.json
7. 23_compliance/evidence/phase2/phase2_decision_log.jsonl
8. 17_observability/score/phase2_status.json

Pflichtinhalt:
- UTC ISO8601 timestamps
- SHA256 hashes für Hauptartefakte
- PASS/FAIL/BLOCKED
- rationale
- evidence refs
- phase3_manifest_candidates
- no fantasy paths
- no unverified claims

Abbruchkriterien:
- Root-24-LOCK-Verstoß
- Manifest-Datei ohne reale Implementierung
- Code-Implementierung statt SoT-Completion
- Registry/logs/locks/manifests/intake-Semantik verletzt
- PII-/Custody-Verstoß

Definition of Done:
- 384/384 Charts vorhanden oder sauber erzeugt
- 384/384 Charts erfüllen Mindesttemplate
- alle MUST-Policies eingetragen
- Governance/Evidence/Observability/Testing pro Chart dokumentiert
- Phase-3-Manifest-Kandidaten markiert
- Phase-2-Status objektiv PASS oder BLOCKED

Finaler Output:
- knapper Abschlussbericht
- Liste erzeugter/geänderter Dateien
- Anzahl Charts pro Statusklasse
- offene Blocker
- SHA256 der Hauptartefakte
- klare Aussage: GLOBAL PHASE 2 PASS oder GLOBAL PHASE 2 BLOCKED
