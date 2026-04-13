# SSID Phase 0 — Acceptance Gates

## Metadata
- generated_at_utc: 2026-03-26T19:13:43Z
- phase: 0
- gate_mode: fail_closed

## PASS nur wenn alle Punkte erfüllt sind

### Gate A — Canonical Source Lock
- [ ] Tier-0-Quellen vollständig inventarisiert
- [ ] Tier-0-Quellen gehasht
- [ ] Tier-0-Quellen in Freeze-Report eingetragen
- [ ] Keine konkurrierende SoT als gleichrangig markiert

### Gate B — Repo Role Lock
- [ ] SSID als kanonisches Hauptrepo dokumentiert
- [ ] SSID-EMS als Betriebs-/Steuerungsschicht dokumentiert
- [ ] SSID-open-core als Public Mirror dokumentiert
- [ ] SSID-docs als Public Docs dokumentiert

### Gate C — Structure & Policy Lock
- [ ] ROOT-24-LOCK referenziert
- [ ] SAFE-FIX referenziert
- [ ] NEU gewinnt / ALT nur Evidence dokumentiert
- [ ] chart.yaml=WAS / manifest.yaml=WIE dokumentiert

### Gate D — Standards Baseline
- [ ] DID Core 1.0 aufgenommen
- [ ] VC Data Model 2.0 aufgenommen
- [ ] OpenID4VCI 1.0 aufgenommen
- [ ] OpenID4VP 1.0 aufgenommen
- [ ] EUDI/eIDAS 2 aufgenommen

### Gate E — Regulatory Baseline
- [ ] MiCA-Baseline dokumentiert
- [ ] AI-Act-Baseline dokumentiert
- [ ] DSGVO/eIDAS-Bezug dokumentiert
- [ ] Launch-relevante Compliance-Grenzen dokumentiert

### Gate F — Evidence & Registry
- [ ] phase0_registry_lock.json erzeugt
- [ ] phase0_canonical_freeze_report.json erzeugt
- [ ] phase0_source_hashes.json erzeugt
- [ ] phase0_decision_log.jsonl erzeugt
- [ ] phase0_status.json erzeugt

### Gate G — Drift/Conflict Resolution
- [ ] alte konkurrierende Strukturen als Evidence-only markiert
- [ ] keine offene Mehrdeutigkeit in Naming/Repo-Rollen
- [ ] keine offene Mehrdeutigkeit bei Standards/Legal-Baseline

## BLOCKER
- Mehr als eine gleichrangige SoT
- Ungeklärte Repo-Rollen
- Manifest-Erzeugung ohne reale Implementierung
- Root-/Depth-/Policy-Verstoß
- Public/OpenCore-Aktivität vor Abschluss von Phase 0
