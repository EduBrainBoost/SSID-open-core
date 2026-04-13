# Phase 2 Acceptance Gates

## PASS nur wenn
- 384/384 chart.yaml vorhanden
- alle 384 Charts enthalten alle Pflichtblöcke
- alle MUST-Policies enthalten
- Governance + Evidence + Observability + Testing enthalten
- keine Manifest-Datei ohne reale Implementierung erzeugt
- Registry-/Evidence-Dateien am korrekten Pfad
- Cross-root Konsistenzcheck grün

## BLOCKED wenn
- weniger als 384 Charts vorhanden
- ein Root unvollständig
- Policies/Governance/Evidence fehlen
- registry/logs / locks / manifests / intake semantisch verletzt
- Phase 2 in Implementierungsphase abdriftet

## Evidence
- phase2_chart_completion_audit.json
- phase2_decision_log.jsonl
- phase2_chart_completion_manifest.json
- phase2_chart_gap_matrix.json
- phase2_status.json
