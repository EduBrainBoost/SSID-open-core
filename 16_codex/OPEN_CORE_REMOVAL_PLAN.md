# FORBIDDEN INVENTORY - ZU ENTFERNEN
Erstellt: 2026-04-15

Folgende Dateien und Verzeichnisse werden aus SSID-open-core entfernt:

✅ Caches und Build Artefakte:
- `**/__pycache__/*`
- `**/*.pyc`
- `.pytest_cache/*`

✅ Operative Runtime Dateien:
- `24_meta_orchestration/registry/*`
- `24_meta_orchestration/report_bus/*`
- `24_meta_orchestration/tsar/*`
- `24_meta_orchestration/incident/*`
- `24_meta_orchestration/triggers/*`
- `24_meta_orchestration/version_management/*`

✅ Backups und Exporte:
- `backup_denied_roots_*.tar.gz`
- `ssid_open_core_export.zip`
- `ssid_open_core_export/*`

✅ Evidence und Audit Artefakte:
- `DEPLOYMENT_EVIDENCE.md`
- `GOVERNANCE_AUDIT_FINAL_REPORT.md`
- `LOCAL_ONLY_VERIFICATION_POLICY.md`
- `BOUNDARY_VIOLATIONS_PHASE1.txt`

Alle oben genannten Elemente verletzen die Open-Core Boundary Policy.
Diese Dateien werden manuell entfernt oder durch einen CI Gate blockiert.
