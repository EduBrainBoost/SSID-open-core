# ADR 001: SSID-open-core Boundary Canon
Stand: 2026-04-15
Status: VORLÄUFIG, PHASE 2

## 1. KANONISCHE BOUNDARY REGEL

SSID-open-core ist eine kuratierte public-safe Export-Oberfläche. Es ist KEIN Dump des privaten SSID Repos.

### Erlaubte Surface (Allowlist)
| Root | Erlaubte Pfade |
|------|----------------|
| 03_core | `03_core/validators/sot/` |
| 12_tooling | `12_tooling/cli/`, `12_tooling/scripts/`, `12_tooling/tests/export/` |
| 16_codex | `16_codex/decisions/`, `16_codex/contracts/sot/`, `16_codex/open_core_registry.json` |
| 23_compliance | `23_compliance/policies/sot/`, `23_compliance/exceptions/`, `23_compliance/policies/open_core_export_allowlist.yaml` |
| 24_meta_orchestration | `24_meta_orchestration/dispatcher/` |

### STRIKT VERBOTEN (DENYLIST)
✅ Alle anderen Pfade sind standardmäßig verboten
✅ `*/shards/*` -> VERBOTEN
✅ `24_meta_orchestration/registry/*` -> VERBOTEN
✅ `24_meta_orchestration/report_bus/*` -> VERBOTEN
✅ `02_audit_logging/*` -> VERBOTEN
✅ Evidence-Dateien, Dry Runs, Deletion Manifeste -> VERBOTEN
✅ Caches, Build Artefakte, Backups -> VERBOTEN
✅ Internen Pfade, lokale Referenzen -> VERBOTEN

## 2. GOVENANCE REGELN
- Einzig erlaubtes Boundary Modell: diese Allowlist
- Keine Erweiterungen ohne explizite ADR
- Alle Dateien im Repo müssen entweder in der Allowlist stehen oder werden entfernt
- Drift wird fail-closed in CI blockiert
