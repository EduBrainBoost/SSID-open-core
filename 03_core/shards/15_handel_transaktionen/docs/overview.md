# Handel & Transaktionen -- Technische Uebersicht (Core)

## Funktion

Handels-Validierung und Transaktions-Integritaetspruefung.
Verarbeitet ausschliesslich gehashte Daten (SHA3-256) gemaess Non-Custodial-Prinzip.

## Abhaengigkeiten

- `03_core/shards/15_handel_transaktionen/chart.yaml` -- Shard-Konfiguration
- `03_core/interfaces/` -- Validierungs-Bus
- `17_observability/logs/03_core/` -- Log-Ausgabe
- `23_compliance/evidence/03_core/` -- Evidence-Pfad

## Governance

Alle Aenderungen erfordern einen RFC-Prozess. PII-Speicherung ist verboten.
Quarterly Bias-Audits sind fuer AI-Komponenten erforderlich.
