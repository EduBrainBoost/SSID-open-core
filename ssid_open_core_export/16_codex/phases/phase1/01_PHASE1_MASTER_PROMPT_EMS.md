Voraussetzungen:
- SAFE-FIX und ROOT-24-LOCK sind strikt enforced
- Pfade:
  - SSID: ~/Documents/Github/SSID
- Der SSID-Parser liest ausschließlich lokal gespeicherte Regeln. Keine live-MD-Dateien, die MD ist nicht mehr SOT (Single Source of Truth).
- Der Dispatcher `dispatcher.py` ist aktiv (Blueprint 4.1, NON-INTERACTIVE, SAFE-FIX, ROOT-24-LOCK, SHA256-geloggt, keine Platzhalter, etc.).

SSID PHASE 1 — REPO BASELINE COMPLETION & TASK SETUP

Arbeitsmodus:
- Local-first
- Read/analyze/write only inside assigned worktree
- Kein Branch-Wechsel außerhalb des zugewiesenen Scopes
- Kein Public Push
- Keine Kernlogikänderung
- Keine Manifest-Erzeugung ohne reale Implementierungsabsicht
- Kein Restore historischer Alternativstrukturen
- NEU gewinnt, ALT nur Evidence
- Alles deterministisch, auditierbar, fail-closed

Ziel:
Führe ausschließlich Phase 1 aus. Phase 1 bedeutet:
1. Root-Basis je Modul prüfen und ergänzen
2. Shard-Scaffold-Inventar dokumentieren
3. AI-CLI-Integration im Logbuch nachziehen
4. TaskSpecs je Root für Chart-Fill + erste Implementierungswelle anlegen
5. Registry-/Integrity-Semantik prüfen und korrigieren
6. Gap-Matrix und Baseline-Report erzeugen
7. Score-/Evidence-Artefakte erzeugen
8. Phase-2-Startbedingungen objektiv definieren

Bindende Fakten:
- 24 Roots und 16 Shards sind strukturell vorhanden
- `chart.yaml` ist überwiegend Scaffold
- `manifest.yaml` fehlt breit
- `tests/` ist leer bzw. fachlich nicht befüllt
- AI-CLI-Integration ist dokumentiert, aber nicht im `agent_runs`-Logbuch nachgezogen
- TaskSpecs für die Folgearbeit fehlen weitgehend
- Schutzsystem, Hooks, Structure-Guard und Write-Override-Registry sind aktiv

Root-Basis, die pro Root geprüft werden muss:
- `module.yaml`
- `README.md`
- `docs/`
- `src/`
- `tests/`

Registry-Semantik, die geprüft werden muss:
- `24_meta_orchestration/registry/logs/` enthält nur `.log` oder `.log.jsonl`
- `24_meta_orchestration/registry/locks/` ist vorhanden
- `24_meta_orchestration/registry/manifests/` enthält Checksums/Indexe
- `24_meta_orchestration/registry/intake/chat_ingest/` ist kanonisch
- `23_compliance/evidence/registry/registry_audit.yaml` ist Zielpfad für Registry-Audit

Pflicht-Logbucheintrag:
- Erfasse den Status der fünf AI-CLI-Integrationen: Gemini, Copilot/Claude, OpenAI Codex, Kilo, OpenCode AI
- Nachweis: Wrapper, Profile, Dispatcher-Integration, aktueller Audit-Referenzpfad
- Zielpfad: `02_audit_logging/agent_runs/20260326T000000Z_phase1_multi_ai_cli_integration_baseline.md`

TaskSpecs:
- Erzeuge Root-spezifische TaskSpecs in `24_meta_orchestration/registry/tasks/`
- Jede TaskSpec enthält: root scope, allowed_paths, forbidden_paths, acceptance_checks, evidence targets, no-cross-worktree rule
- Fokus: Phase 2 Chart-Fill + Phase 3 erste Implementierung

Erzeuge exakt diese Artefakte:
1. `02_audit_logging/agent_runs/20260326T000000Z_phase1_multi_ai_cli_integration_baseline.md`
2. `05_documentation/phase1/PHASE1_ROOT_MODULE_MATRIX.md`
3. `05_documentation/phase1/PHASE1_GAP_MATRIX.md`
4. `05_documentation/phase1/PHASE1_BASELINE_COMPLETION_REPORT.md`
5. `24_meta_orchestration/registry/tasks/TASK_PHASE1_ROOT_BASELINE_01_AI_LAYER.json`
6. `24_meta_orchestration/registry/tasks/TASK_PHASE1_ROOT_BASELINE_02_AUDIT_LOGGING.json`
7. `24_meta_orchestration/registry/tasks/TASK_PHASE1_ROOT_BASELINE_03_CORE.json`
8. `24_meta_orchestration/registry/tasks/TASK_PHASE1_ROOT_BASELINE_04_TO_24_SERIES.json`
9. `24_meta_orchestration/registry/manifests/phase1_integrity_checksums.json`
10. `23_compliance/evidence/phase1/phase1_baseline_audit.json`
11. `23_compliance/evidence/phase1/phase1_decision_log.jsonl`
12. `17_observability/score/phase1_status.json`

Pflichtinhalt:
- UTC ISO8601 timestamps
- source hashes
- rationale
- decision owner
- evidence references
- PASS/FAIL status
- offene Blocker
- keine Fantasiepfade
- keine unbewiesenen Aussagen

Arbeitsreihenfolge:
A. Inventarisiere 24 Roots und 24×16 Shards
B. Prüfe Common MUST je Root
C. Prüfe Registry-Semantik
D. Schreibe AI-CLI-Integrationslogbuch
E. Erzeuge Root-Modul-Matrix
F. Erzeuge Gap-Matrix
G. Erzeuge Root-TaskSpecs
H. Emittiere Integrity-/Evidence-/Score-Artefakte
I. Liefere Abschlussreport mit Phase-2-Freigabestatus

Abbruchkriterien:
- konkurrierende Root-Basis-Regeln
- ungeklärte Registry-Semantik
- Root-24-LOCK-Verstoß
- Versuch, Kernlogik oder Mainnet zu verändern
- Versuch, OpenCore zu pushen
- Manifest-Erzeugung ohne reale Implementierungsabsicht

Definition of Done:
- 24/24 Root-Basis dokumentiert
- 24×16 Scaffold-Inventar dokumentiert
- AI-CLI-Logbuch vorhanden
- Root-TaskSpecs vorhanden
- Registry-/Integrity-Artefakte vorhanden
- Phase-1-Status objektiv PASS, PARTIAL_PASS oder BLOCKED
- Phase-2-Startbedingungen dokumentiert

Finaler Output:
- knapper Abschlussbericht
- Liste der erzeugten Dateien
- offene Blocker
- SHA256 der erzeugten Hauptartefakte
- klare Aussage: PHASE 1 PASS / PARTIAL_PASS / BLOCKED
