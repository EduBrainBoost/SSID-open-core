# Versicherungen & Risiken -- Technische Uebersicht (Core)

## Funktion

Versicherungsdaten-Validierung und Risiko-Policy-Pruefung.
Verarbeitet ausschliesslich gehashte Daten (SHA3-256) gemaess Non-Custodial-Prinzip.

## Abhaengigkeiten

- `03_core/shards/11_versicherungen_risiken/chart.yaml` -- Shard-Konfiguration
- `03_core/interfaces/` -- Validierungs-Bus
- `17_observability/logs/03_core/` -- Log-Ausgabe
- `23_compliance/evidence/03_core/` -- Evidence-Pfad

## Governance

Alle Aenderungen erfordern einen RFC-Prozess. PII-Speicherung ist verboten.
Quarterly Bias-Audits sind fuer AI-Komponenten erforderlich.
