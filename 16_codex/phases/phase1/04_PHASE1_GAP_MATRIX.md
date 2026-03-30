# SSID Phase 1 — Gap Matrix

## Priorisierte Lücken
| Priorität | Bereich | Ist-Befund | Zielzustand nach Phase 1 | Phase-2/3 Folge |
|---|---|---|---|---|
| P0 | AI-CLI Logbuch | Integration dokumentiert, aber kein `agent_runs`-Eintrag | Logbucheintrag vorhanden | EMS-/Dispatcher-Nachweis belastbar |
| P0 | Root TaskSpecs | nur minimale Task-Basis | TaskSpecs je Root vorhanden | Chart-Fill startbar |
| P0 | Registry-Semantik | Pfade/Dateitypen müssen auf Level-3 geprüft werden | `logs/`, `locks/`, `manifests/`, `intake/` validiert | Gates belastbar |
| P1 | Charts | `chart.yaml` scaffold-only | Gap dokumentiert, Root-Zuordnung fix | Phase 2 Chart-Fill |
| P1 | Manifeste | `manifest.yaml` fehlt breit | Manifest-Strategie dokumentiert, keine Fake-Manifeste | Phase 3 Implementierungen |
| P1 | Tests | `tests/` leer bzw. fachlich unbefüllt | QA-Baseline und Testpflicht dokumentiert | deterministische Gates |
| P1 | Compliance-Mappings | nicht vollständig materialisiert | Gap dokumentiert, Zielpfade festgelegt | Phase 5 Governance/Compliance |
| P2 | Write-Overrides | zeitlich zu härten | Review + Ablaufregel dokumentiert | laufender Schutzbetrieb |

## Pflichtblocker
- Root-24-LOCK-Verstoß
- fehlende Common-MUST-Basis
- Registry-Semantik-Verstoß
- fehlender AI-CLI-Logbucheintrag
- fehlende Root-TaskSpecs

## Notes
Phase 1 schließt **Baseline-Lücken**. Feature-Bau gehört ab Phase 2/3 in kontrollierte Root-Scopes.
