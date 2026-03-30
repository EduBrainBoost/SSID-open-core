# OPERATOR FLOW — SSID Sub-Orchestrator System

Stand: 2026-03-29 | Task: T-019

---

## Voraussetzungen

- Claude Code CLI aktiv
- SSID-Workspace unter `C:\Users\bibel\SSID-Workspace\SSID-Arbeitsbereich\Github\SSID`
- SSIDCTL Agent Registry geladen (87 Agents, 12 Skills, 11 Worker-Commands)
- Policies unter `24_meta_orchestration/orchestrator/` vorhanden

---

## Schritt 1: Nutzerauftrag kommt rein

Der Operator gibt einen Auftrag in Claude Code ein (Freitext oder strukturiert).

Beispiel: "Erstelle einen neuen Shard unter 09_meta_identity fuer Berufsidentitaeten."

---

## Schritt 2: Task-ID Erzeugung

Claude Code erzeugt automatisch:
- `task_id`: Format `T-{seq}_{epoch}_{sha256_8}`
- SHA256-Hash des Auftragstexts
- Eintrag im append-only Ledger (`task_ledger.jsonl`)
- Repo-Ziel wird zugeordnet (SSID, SSID-EMS, etc.)

Regelwerk: `TASK_INTAKE_POLICY.yaml`

---

## Schritt 3: Routing an Sub-Orchestrator

Anhand des Auftragstyps wird an den zustaendigen Sub-Orchestrator geroutet:

| Sub-Orchestrator | Zustaendig fuer |
|---|---|
| structure_orchestrator | Root-24, Shards, Pfade |
| policy_orchestrator | SoT, Rego, Compliance |
| runtime_orchestrator | ssidctl, Hooks, Worker |
| agent_orchestrator | Registry, Skills, Activation |
| verification_orchestrator | Gates, Tests, Evidence |
| repo_sync_orchestrator | Push, Branch, Worktree |

Regelwerk: `TASK_ROUTING_POLICY.yaml`

---

## Schritt 4: Spezialagenten laufen

Der Sub-Orchestrator dispatcht an die zustaendigen SSIDCTL-Agents:
- Agents arbeiten innerhalb ihres definierten Scope (Layer, Root, Shard)
- Jeder Agent hat gebundene Skills und Tools (siehe `AGENT_SKILL_BINDING_MATRIX.json`)
- Handoffs zwischen Agents folgen dem `INTER_AGENT_HANDOFF_POLICY.yaml`
- Kein freier Chat — nur explizite Uebergaben mit task_id + scope + expected_output

---

## Schritt 5: Verifier pruefen

Nach Abschluss der Agent-Arbeit pruefen die Verifier:

| Verifier | Prueft |
|---|---|
| structure_verifier | Root-24-Integritaet, Pfade |
| policy_verifier | SoT-Konsistenz, Policy-Drift |
| runtime_verifier | Worker-Health, CLI-Status |
| agent_verifier | Registry-Konsistenz |
| repo_sync_verifier | Git-Status, Push-State |
| final_closure_verifier | Alle Gates gruen |

Regelwerk: `VERIFIER_LAYER_REGISTRY.yaml`

---

## Schritt 6: Abschluss mit Commit/Report

- Alle Verifier gruen: Task wird als `completed` markiert
- Commit wird erstellt mit Evidence (SHA256 before/after)
- Report wird in `02_audit_logging/reports/` geschrieben
- Task-Ledger wird aktualisiert

---

## Aktueller Status

### Aktiv (sofort nutzbar)
- 87 SSIDCTL Agents in Registry (`ssidctl_agent_registry.v2.yaml`)
- 12 Skills in `12_tooling/skills/`
- 11 Worker-Commands in `12_tooling/cli/worker_commands/`
- 4 Orchestrator-Policies (WP3, diese Session)
- 1 Agent-Skill-Binding-Matrix (WP4, diese Session)

### Noch zu aktivieren
- Task-Ledger (`task_ledger.jsonl`) — wird beim ersten Task automatisch erstellt
- Handoff-Ledger (`handoff_ledger.jsonl`) — wird beim ersten Handoff automatisch erstellt
- Verifier-Tools: `structure_guard.py` und `sot_validator.py` existieren, muessen in CI integriert werden
- Sub-Orchestrator Runtime: Aktuell Policy-basiert, CLI-Integration ausstehend

### Starten

1. Claude Code im SSID-Workspace oeffnen
2. Auftrag eingeben
3. System routet automatisch anhand der Policies

Kein manuelles Setup noetig — Policies sind deklarativ und werden beim naechsten ssidctl-Lauf geladen.
