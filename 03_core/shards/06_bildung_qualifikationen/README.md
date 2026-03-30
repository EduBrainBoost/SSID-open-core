# Core -- Bildung & Qualifikationen

## Purpose

Bildungsnachweis-Validierung und Qualifikations-Pruefung.
Dieser Shard verwaltet alle Bildung & Qualifikationen-bezogenen Operationen innerhalb des Core-Kontexts.
Er stellt sicher, dass alle Daten non-custodial verarbeitet werden (nur SHA3-256-Hashes).

## Structure

```
06_bildung_qualifikationen/
  chart.yaml          # Shard-Konfiguration und Capabilities
  manifest.yaml       # Deployment-Manifest
  docs/               # Technische Dokumentation
  tests/              # Automatisierte Tests
  implementations/    # Sprachspezifische Implementierungen
    python/src/       # Python-Module
```

## Interfaces

- **Core Validator Bus**: Primaere Schnittstelle fuer Bildung & Qualifikationen-Daten im Core
- **Policy Engine API**: Sekundaere Schnittstelle fuer Abfragen und Validierung

## SoT Reference

Kanonische Konfiguration: `03_core/shards/06_bildung_qualifikationen/chart.yaml`
