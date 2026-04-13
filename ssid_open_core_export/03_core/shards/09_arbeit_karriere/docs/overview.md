# Arbeit & Karriere -- Technische Uebersicht (Core)

## Funktion

Arbeitsverhaeltnis-Validierung und Karrieredaten-Pruefung.
Verarbeitet ausschliesslich gehashte Daten (SHA3-256) gemaess Non-Custodial-Prinzip.

## Abhaengigkeiten

- `03_core/shards/09_arbeit_karriere/chart.yaml` -- Shard-Konfiguration
- `03_core/interfaces/` -- Validierungs-Bus
- `17_observability/logs/03_core/` -- Log-Ausgabe
- `23_compliance/evidence/03_core/` -- Evidence-Pfad

## Governance

Alle Aenderungen erfordern einen RFC-Prozess. PII-Speicherung ist verboten.
Quarterly Bias-Audits sind fuer AI-Komponenten erforderlich.
