# SSIDCTL Agent System v2 — 87-Agenten-Registry

Lesbare Spiegelung der operativen SoT-Quelle:
`24_meta_orchestration/registry/ssidctl_agent_registry.v2.json`

## Architekturueberblick

Das SSIDCTL-System ist ein geschichtetes Agenten-Betriebssystem mit 87 Agents auf 6 Ebenen (L0-L5). Jeder Agent hat einen definierten Scope, erlaubte/verbotene Pfade und deterministische Done-Criteria.

Das System ersetzt nicht das bestehende 29-Agenten-System, sondern wird additiv parallel materialisiert. Die operative Umschaltung erfolgt erst nach separater Freigabe.

## Count-Modell

| Ebene | Anzahl | Zweck |
|-------|--------|-------|
| L0 | 1 | Gesamtsteuerung — Chief Supervisor, Gate-Freigabe, Finalentscheid |
| L1 | 5 | Repo-Verantwortung — je ein Agent pro Repo (SSID, EMS, Orchestrator, Open-Core, Docs) |
| L2 | 24 | Root-Verantwortung — je ein Agent pro kanonischem Root (01-24) |
| L3 | 16 | Shard-/Domaenen-Verantwortung — je ein Agent pro Fachdomaene (Personen, Finanzen, etc.) |
| L4 | 24 | Plattform-Spezialisten — Locks, Gates, Evidence, Config, CI, Forensik, etc. |
| L5 | 17 | Produkt-Spezialisten — DID, VC, Wallet, Auth, Tokenomics, PQC, Incident, etc. |
| **Summe** | **87** | vollstaendiger SSIDCTL-Arbeitsverbund |

## Level-Erklaerung

**L0 — Gesamtsteuerung**: Ein einziger Master-Orchestrator. Entscheidet ueber Gate-Freigaben, konsolidiert Reports, loest Konflikte, liefert Finalverdikt.

**L1 — Repo-Verantwortung**: Je ein Agent pro Repo. Steuert Branch-Hygiene, Diff-Reviews, Build-Disziplin innerhalb des zugewiesenen Repos.

**L2 — Root-Verantwortung**: Je ein Agent pro Root-Ordner (01_ai_layer bis 24_meta_orchestration). Kennt die fachliche Semantik des Roots und alle zugehoerigen Shards.

**L3 — Shard-Verantwortung**: Je ein Agent pro Fachdomaene (16 Shards). Arbeitet uebergreifend ueber mehrere Roots hinweg, fokussiert auf domaenenspezifische SSI-Objekte.

**L4 — Plattform-Spezialisten**: Technische Querschnittsfunktionen: Locking, CI-Gates, Evidence-Versiegelung, Secret-Schutz, Sandbox-Steuerung, Forensik, etc.

**L5 — Produkt-Spezialisten**: Tiefe Spezialisierung auf Produktfunktionen: DID-Method, VC-Issuance/Verification, Wallet, WebAuthn, Tokenomics, PQC-Migration, Incident-Response, etc.

## Dateiliste

| Artefakt | Pfad |
|----------|------|
| Registry (87 Agents) | `24_meta_orchestration/registry/ssidctl_agent_registry.v2.json` |
| Activation Profiles | `24_meta_orchestration/registry/ssidctl_activation_profiles.v2.json` |
| Legacy Mapping | `24_meta_orchestration/registry/ssidctl_legacy_mapping.v2.json` |
| JSON Schema | `24_meta_orchestration/registry/ssidctl_agent_registry.schema.json` |
| Doku-Spiegel | `16_codex/agents/SSIDCTL_AGENT_SYSTEM_V2.md` |
| Migration Plan | `05_documentation/agents/SSIDCTL_MIGRATION_PLAN_V2.md` |
| Tests | `11_test_simulation/tests_meta/test_ssidctl_agent_registry.py` |
| Audit Report | `02_audit_logging/reports/SSIDCTL_AGENT_REGISTRY_AUDIT_V2.json` |
| Score/Status | `17_observability/score/ssidctl_agent_registry_status.json` |

## Activation Profiles

| Profil | Agents | Beschreibung |
|--------|--------|-------------|
| full_87 | 87 | Vollstaendiger Verbund |
| gate55_core_11 | 11 | Gate-5.5-Stabilisierung |
| repo_ssid_only | 32 | Nur SSID-Hauptrepo |
| ems_runtime_only | 12 | EMS + Orchestrator Runtime |
| identity_core_phase6 | 21 | DID/VC/Wallet/Auth Produktkern |
| docs_registry_only | 14 | Docs + Registry + Audit |
| legacy_29_compat | 32 | Alt-System-Kompatibilitaet |

## Legacy-29 zu V2 Mapping

Die 29 bestehenden Agenten (legacy_v1) werden nicht geloescht oder modifiziert. Stattdessen existiert ein vollstaendiges Mapping in `ssidctl_legacy_mapping.v2.json`, das jede Legacy-Rolle einem oder mehreren v2-Agents zuordnet.

Mapping-Strategien:
- **direct** — 1:1 Abbildung auf einen v2-Agent
- **split** — Aufspaltung in mehrere spezialisierte v2-Agents
- **distribute** — Verteilung auf scope-spezifische v2-Agents
- **absorb** — Funktion wird Teil eines uebergeordneten v2-Agents
- **legacy-only** — kein Aequivalent in v2, nur via legacy_29_compat nutzbar

## Betriebsregeln

1. Legacy bleibt erhalten und lesbar
2. v2 ist additiv — keine Ueberschreibung bestehender Dateien
3. Keine Runtime-Umschaltung in diesem Materialisierungslauf
4. Umschaltung erst nach: Tests PASS + Schema-Validierung PASS + Runtime-Loader bereit + explizite Freigabe
5. Alle Agents: `can_touch_canonical: false`
6. Workspace-Root: `C:\Users\bibel\SSID-Workspace\SSID-Arbeitsbereich\Github`
7. Canonical-Zone: `C:\Users\bibel\Documents\Github` (nur Referenz, keine KI-Schreibarbeit)
