Voraussetzungen:
- SAFE-FIX und ROOT-24-LOCK sind strikt enforced
- Pfade:
  - SSID: ~/Documents/Github/SSID
- Der SSID-Parser liest ausschließlich lokal gespeicherte Regeln. Keine live-MD-Dateien, die MD ist nicht mehr SOT (Single Source of Truth).
- Der Dispatcher `dispatcher.py` ist aktiv (Blueprint 4.1, NON-INTERACTIVE, SAFE-FIX, ROOT-24-LOCK, SHA256-geloggt, keine Platzhalter, etc.).

SSID PHASE 3 — MANIFEST MATERIALIZATION

Arbeitsmodus:
- Local-first
- Ein Chat = ein Scope = ein Branch = ein Worktree
- Kein Branch-Wechsel außerhalb des zugewiesenen Worktrees
- Kein Public Push
- Keine Kernlogikänderung
- Kein Manifest ohne reale Implementierung
- Kein Restore historischer Alternativstrukturen
- NEU gewinnt, ALT nur Evidence
- Alles deterministisch, auditierbar, fail-closed

Ziel:
Führe ausschließlich Global Phase 3 aus. Phase 3 bedeutet:
1. implementation-ready shards objektiv identifizieren
2. Manifest-Eignung je Root × Shard bewerten
3. `manifest.yaml` nur für reale Implementierungen materialisieren
4. chart/manifest/contracts/tests/registry/evidence parity sicherstellen
5. Registry-/Audit-/Score-Artefakte erzeugen
6. Phase-4-Startbedingungen dokumentieren

Verbindliche Regeln:
- `chart.yaml` = WAS
- `manifest.yaml` = WIE
- Contract-first development
- 24 Roots fix
- 16 Shards pro Root
- No fake manifests
- No manifest for scaffold-only shard
- Hash-only / non-custodial
- Provider-direct verification model
- EMS-first for control and verification

Readiness-Klassen:
- READY_FOR_MANIFEST
- BLOCKED_NO_IMPLEMENTATION
- BLOCKED_NO_CONTRACTS
- BLOCKED_NO_TESTS
- BLOCKED_NO_REGISTRY
- BLOCKED_POLICY_MISMATCH
- BLOCKED_EVIDENCE_MISSING

Pflichtprüfung pro kandidatfähigem Shard:
A. `chart.yaml` vorhanden
B. `implementations/` enthält reale Implementierung
C. Contracts/Schemas referenzierbar
D. Tests vorhanden oder deterministisch nachgezogen
E. Registry-Eintrag vorhanden oder im selben Scope erzeugbar
F. Policy-Constraints kompatibel
G. Evidence-Pfade definiert

Erzeuge exakt diese Artefakte:
1. 05_documentation/phase3/PHASE3_MANIFEST_ELIGIBILITY_MATRIX.md
2. 05_documentation/phase3/PHASE3_MANIFEST_TEMPLATE_SPEC.md
3. 05_documentation/phase3/PHASE3_IMPLEMENTATION_READINESS_MATRIX.csv
4. 24_meta_orchestration/registry/phase3_manifest_registry.json
5. 23_compliance/evidence/phase3/phase3_manifest_audit_report.json
6. 23_compliance/evidence/phase3/phase3_manifest_hashes.json
7. 23_compliance/evidence/phase3/phase3_manifest_decision_log.jsonl
8. 17_observability/score/phase3_status.json

Zusätzlich:
- Materialisiere `manifest.yaml` ausschließlich für READY_FOR_MANIFEST shards
- Jeder erzeugte Manifest-Pfad muss auf einen realen Implementierungsordner zeigen
- Jeder Manifest-Eintrag muss Dependencies, Runtime, Tests, Evidence, Registry-Referenz und Chart-Referenz enthalten
- Keine Fantasiepfade
- Keine unbewiesenen Aussagen

Arbeitsreihenfolge:
A. Inventarisiere alle Shards
B. Prüfe Implementation Presence
C. Prüfe Contract/Test/Registry/Evidence-Parität
D. Klassifiziere alle Kandidaten
E. Erzeuge nur zulässige manifests
F. Aktualisiere Registry + Evidence
G. Bewerte Gate-Status
H. Liefere Abschlussreport

Abbruchkriterien:
- Manifest ohne reale Implementierung
- konkurrierende SoT
- Root-24-LOCK-Verstoß
- fehlende Chart-Referenz
- fehlende Test-/Evidence-Referenz
- Versuch, OpenCore/Mainnet mitzuschreiben

Definition of Done:
- alle 384 Shards klassifiziert
- nur reale Implementierungen erhalten `manifest.yaml`
- Registry-/Audit-/Score-Artefakte erzeugt
- Phase-3-Status objektiv PASS oder BLOCKED ausgewiesen
- Phase-4-Startbedingungen dokumentiert

Finaler Output:
- knapper Abschlussbericht
- Liste der erzeugten Dateien
- READY_FOR_MANIFEST / BLOCKED-Zahlen
- SHA256 der Hauptartefakte
- klare Aussage: PHASE 3 PASS oder PHASE 3 BLOCKED
