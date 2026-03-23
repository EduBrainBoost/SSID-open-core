# SSID-open-core — Repo-Regeln

## REPO-IDENTITAET
- Repo-Name: SSID-open-core
- Repo-Pfad: C:\Users\bibel\SSID-Workspace\Github\SSID-open-core
- Primaerer Branch: main
- Arbeits-Branches: develop, feature/*, fix/*

## WRITE-SCOPE
Nur innerhalb dieses Repos schreiben.
Dieses Repo enthaelt oeffentliche Bibliotheken, SDKs und APIs — kein interner SSID-Kerncode.

## VERBOTENE PFADE
- Andere Repos (SSID, SSID-EMS, SSID-orchestrator, SSID-docs)
- .git/ direkt beschreiben
- Globale .ssid-system/ Dateien ohne L0-Freigabe
- Interne Implementierungsdetails des SSID-Hauptrepos hier ablegen

## INHALT UND ZWECK
- Oeffentliche APIs und Typdefinitionen fuer alle SSID-Repos
- Wiederverwendbare Bibliotheken und SDKs
- Gemeinsame Utilities und Helper-Module
- Kein interner/proprietaerer SSID-Kerncode

## VERSIONIERUNG
SemVer wird strikt eingehalten. Breaking Changes (Major) erfordern L0-Freigabe und
koordiniertes Update in allen Konsumenten-Repos (SSID-EMS, SSID-orchestrator).

## PORTS
Dieses Repo hat keine direkten Ports. Bibliotheken und SDKs betreiben keine eigenen Server.

## SAFE-FIX
SAFE-FIX ist permanent aktiv (NON-INTERACTIVE, SHA256-geloggt).
Alle Schreibvorgaenge werden im Evidence-Verzeichnis protokolliert.
