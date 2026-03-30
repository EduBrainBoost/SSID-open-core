# Claude Code als Top-Orchestrator — Operator-Anleitung

**Task-ID:** T-019
**Stand:** 2026-03-29
**Schema-Version:** 1.0.0

---

## 1. Rolle

Claude Code ist der Layer-0 (L0) Top-Orchestrator des SSID-Systems. Alle Aufgaben fliessen durch L0. Kein Agent darf ohne L0-Routing arbeiten.

## 2. Architektur

```
L0: Claude Code (Top-Orchestrator)
  |
  +-- structure_orchestrator    (25 Agents: Root-24, Shards, Manifests)
  +-- policy_orchestrator       (18 Agents: SoT, Compliance, Crypto)
  +-- runtime_orchestrator      (19 Agents: CLI, Config, Infra, Workers)
  +-- agent_orchestrator        ( 4 Agents: Registry, Routing, State)
  +-- verification_orchestrator (13 Agents: Tests, CI, Evidence, Metrics)
  +-- repo_sync_orchestrator    ( 9 Agents: Repo-Sync, Forensics, Export)
  |
  +-- 11 Worker Commands (supervisor, dispatch, build, test, browser,
                          policy, audit, registry, provider, release, repair)
```

## 3. Task-Lifecycle

1. **INTAKE**: L0 empfaengt Task mit Task-ID + Repo-Ziel
2. **ROUTING**: L0 waehlt Sub-Orchestrator basierend auf Scope
3. **DISPATCH**: Sub-Orchestrator waehlt L2-L5 Agent
4. **EXECUTION**: Agent fuehrt aus, erzeugt Evidence
5. **VERIFICATION**: Verifier prueft Ergebnis
6. **CLOSURE**: L0 versiegelt Evidence, aktualisiert Ledger

## 4. Vor jedem Lauf pruefen

- [ ] Task-ID vorhanden? (T-XXX Format)
- [ ] Repo-Ziel definiert? (SSID, SSID-EMS, SSID-orchestrator, SSID-open-core, SSID-docs)
- [ ] Sub-Orchestrator identifiziert?
- [ ] Verifier zugewiesen?
- [ ] Lock verfuegbar?

## 5. Policies (HARD_BLOCK)

| # | Policy | Enforcement |
|---|--------|-------------|
| P01 | Kein Lauf ohne Task-ID | REJECT |
| P02 | Kein Lauf ohne Repo-Ziel | REJECT |
| P03 | Kein Agent ohne Sub-Orchestrator | REJECT |
| P04 | Kein Abschluss ohne Verifier | BLOCK_COMPLETION |
| P05 | Kein stilles Droppen | AUDIT_ALERT |
| P06 | "gleich" nur bei Hash-Match | REJECT_CLAIM |
| P07 | append-only task ledger | INTEGRITY_ALERT |
| P08 | Evidence auf jedem Write | BLOCK_WRITE |
| P09 | ROOT-24-LOCK | REJECT |
| P10 | SAFE-FIX only | BLOCK_WRITE |
| P11 | Kein Fake-Success | REJECT_CLAIM |
| P12 | Ein Scope = ein Lock | BLOCK_WRITE |

## 6. Sub-Orchestrator-Zuordnung

| Aufgabentyp | Sub-Orchestrator |
|---|---|
| Root/Shard-Struktur, Manifests, DID/VC | structure_orchestrator |
| SoT, Policy, Compliance, Regulatorik, Crypto | policy_orchestrator |
| CLI, Config, Infra, Dependencies, Provider | runtime_orchestrator |
| Agent-Registry, Skills, Routing, State | agent_orchestrator |
| Tests, CI-Gates, Evidence, Metrics, Incidents | verification_orchestrator |
| Repo-Sync, Forensics, Push, Export | repo_sync_orchestrator |

## 7. Worker-Nutzung

Worker werden via `ssidctl` CLI angesteuert:

```bash
python -m ssidctl.commands.supervisor   # Ueberwachung
python -m ssidctl.commands.dispatch     # Task-Verteilung
python -m ssidctl.commands.build        # Builds
python -m ssidctl.commands.test         # Tests
python -m ssidctl.commands.browser      # Browser-Verifikation
python -m ssidctl.commands.policy       # Policy-Checks
python -m ssidctl.commands.audit        # Audits
python -m ssidctl.commands.registry     # Registry-Verwaltung
python -m ssidctl.commands.provider     # Provider-Management
python -m ssidctl.commands.release      # Release-Gates
python -m ssidctl.commands.repair       # Reparaturen
```

## 8. Evidence-Pflicht

Jeder Schreibvorgang:
1. SHA-256 des bestehenden Inhalts berechnen (oder null bei neuer Datei)
2. Schreibvorgang ausfuehren
3. SHA-256 des neuen Inhalts berechnen
4. Evidence-Eintrag in Ledger schreiben

## 9. Dateien in diesem Verzeichnis

| Datei | Zweck |
|---|---|
| `AGENT_RUNTIME_MATRIX.json` | Vollstaendige Inventur aller 87+11 Agents |
| `ORCHESTRATOR_HIERARCHY.yaml` | L0-L5 Hierarchie mit Agent-Zuordnungen |
| `TOP_ORCHESTRATOR_POLICY.yaml` | 12 HARD_BLOCK Policies fuer L0 |
| `SUB_ORCHESTRATOR_REGISTRY.yaml` | 6 Sub-Orchestratoren mit Scope/Agents |
| `CLAUDE_CODE_BOOTSTRAP.md` | Diese Anleitung |
| `AGENT_CONFIG_AUDIT.md` | Vollstaendigkeits-Audit |

## 10. Referenzen

- Kanonische Agent-Registry: `24_meta_orchestration/registry/ssidctl_agent_registry.v2.yaml`
- Unified Registry: `24_meta_orchestration/registry/ssidctl_unified_agent_registry.yaml`
- Skill-Registry: `24_meta_orchestration/agentswarm/registry/skill_registry.yaml`
- Worker-Commands: `12_tooling/cli/worker_commands/`
- Skills-Implementierung: `12_tooling/skills/`
