# RELEASE GATE POLICY
Stand: 2026-04-15

## Release Anforderungen

### Für jeden Release (Patch, Minor, Major):

| Prüfung | Status | Verantwortlichkeit |
|--------|--------|-------------------|
| Boundary Gate Test | ✅ MUSS PASSEN | CI Automatisch |
| Drift Detection | ✅ MUSS PASSEN | CI Automatisch |
| Export Validierung | ✅ MUSS PASSEN | CI Automatisch |
| Version Parität | ✅ MUSS PASSEN | CI Automatisch |
| Keine Secrets | ✅ MUSS PASSEN | CI Automatisch |

### Release Typ Regeln:

| Release Type | Voraussetzung |
|-------------|--------------|
| Patch (0.1.x) | Boundary + Drift Tests passen |
| Minor (0.x.0) | Testnet PREPARED |
| Major (1.0.0) | Testnet PROVEN + Mainnet MISSING bis nachgewiesen |

### Verbotene Claims im Release:
- "Production use" ohne PROVEN Testnet
- "Mainnet ready" ohne live Nachweis
- "Verified" ohne Explorer Link + Tx Hash

### Release Checkliste vor Publishing:
1. Alle CI Tests grün
2. Version in pyproject.toml aktualisiert
3. CHANGELOG.md aktualisiert
4. TESTNET_STATUS.md geprüft
5. Keine verbotenen Claims in README