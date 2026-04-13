# SSID Phase 1 — Acceptance Gates

## Metadata
- phase: 1
- gate_mode: fail_closed

## PASS nur wenn alle Punkte erfüllt sind

### Gate A — Root Common MUST
- [ ] 24/24 Roots inventarisiert
- [ ] Common MUST je Root geprüft
- [ ] Fehlstellen dokumentiert oder SAFE-FIX-konform ergänzt
- [ ] Keine Root-24-LOCK-Abweichung

### Gate B — Shard Scaffold Inventory
- [ ] 24×16 Shard-Inventar dokumentiert
- [ ] `chart.yaml`-Status je Root erfasst
- [ ] fehlende `manifest.yaml`-Strategie dokumentiert
- [ ] Test-Baseline je Root erfasst

### Gate C — Registry Semantics
- [ ] `registry/logs/` nur `.log` / `.log.jsonl`
- [ ] `registry/locks/` vorhanden
- [ ] `registry/manifests/` vorhanden
- [ ] `registry/intake/chat_ingest/` vorhanden/korrekt
- [ ] `registry_audit.yaml` auf Evidence-Zielpfad geprüft

### Gate D — Audit Logbook
- [ ] AI-CLI-Logbucheintrag in `02_audit_logging/agent_runs/` geschrieben
- [ ] Gemini erfasst
- [ ] Copilot/Claude erfasst
- [ ] OpenAI Codex erfasst
- [ ] Kilo erfasst
- [ ] OpenCode AI erfasst

### Gate E — Task Setup
- [ ] Root-TaskSpecs erzeugt
- [ ] allowed_paths enthalten nur Scope-Pfade
- [ ] acceptance_checks enthalten Chart-Fill + erste Implementierung + Gates
- [ ] evidence targets definiert

### Gate F — Evidence & Score
- [ ] phase1_integrity_checksums.json erzeugt
- [ ] phase1_baseline_audit.json erzeugt
- [ ] phase1_decision_log.jsonl erzeugt
- [ ] phase1_status.json erzeugt
- [ ] Badge/Report synchron

## BLOCKER
- Root-24-LOCK-Verstoß
- Root Common MUST fehlt
- Registry-Semantik verletzt
- AI-CLI-Logbuch fehlt
- TaskSpecs fehlen
- unzulässige Phase-1-Featurearbeit
