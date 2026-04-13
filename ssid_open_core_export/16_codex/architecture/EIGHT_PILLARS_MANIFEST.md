# SSID 8-Saeulen Architektur-Manifest

**Stand:** 2026-03-28
**Version:** 1.0.0
**Status:** Kanonisch

---

## Ueberblick

Die SSID-Architektur basiert auf acht tragenden Saeulen, die gemeinsam ein vollstaendig verifizierbares, selbst-souveraenes Identitaetssystem bilden. Jede Saeule ist durch konkrete Implementierungen und Beweispfade abgesichert.

---

## Die 8 Saeulen

| Saeule | Implementierung | Beweis |
|--------|----------------|--------|
| 1. Wahrheit | SOT Validator, sot_master_merged.json | 03_core/validators/sot/ |
| 2. Struktur | ROOT-24-LOCK, Structure Guard | 12_tooling/scripts/structure_guard.sh |
| 3. Kontrolle | Dispatcher v4.1, SAFE-FIX | 24_meta_orchestration/dispatcher/ |
| 4. Kryptografie | SHA256 Evidence, PQC Module | 21_post_quantum_crypto/ |
| 5. CI/CD + Registry | 23 Workflows, Agent Registry | .github/workflows/ |
| 6. Audit + Beweis | WORM Evidence (19882 Eintraege) | 02_audit_logging/ |
| 7. Governance + Recht | 13 Rego Policies, Compliance | 23_compliance/policies/ |
| 8. Selbstanpassung | TSAR Engine | 24_meta_orchestration/tsar/ |

---

## Saeule 1: Wahrheit (Source of Truth)

**Prinzip:** Es gibt genau eine kanonische Wahrheitsquelle fuer die gesamte Systemdefinition.

- **SOT Validator:** Prueft alle Konfigurationen gegen die Single Source of Truth
- **sot_master_merged.json:** Die zusammengefuehrte kanonische Referenzdatei
- **Beweispfad:** `03_core/validators/sot/`
- **Garantie:** Keine Abweichung von der SOT wird toleriert

---

## Saeule 2: Struktur (ROOT-24-LOCK)

**Prinzip:** Die Systemstruktur ist eingefroren und unveraenderlich.

- **ROOT-24-LOCK:** 24 Root-Ordner sind kanonisch und duerfen weder erstellt, umbenannt noch geloescht werden
- **Structure Guard:** Automatisierte Pruefung der Strukturintegritaet
- **Beweispfad:** `12_tooling/scripts/structure_guard.sh`
- **Garantie:** Kein Agent und kein Prozess kann die Root-Struktur veraendern

---

## Saeule 3: Kontrolle (Dispatcher + SAFE-FIX)

**Prinzip:** Jede Systemaktion wird kontrolliert, protokolliert und ist nachvollziehbar.

- **Dispatcher v4.1:** NON-INTERACTIVE Modus, SHA256-Logging (Blueprint 4.1)
- **SAFE-FIX:** Additives Schreiben, kein blindes Ueberschreiben, Evidence-Pflicht
- **Beweispfad:** `24_meta_orchestration/dispatcher/`
- **Garantie:** Keine unkontrollierte Aenderung am System moeglich

---

## Saeule 4: Kryptografie (SHA256 + Post-Quantum)

**Prinzip:** Alle Beweise und Identitaeten sind kryptografisch abgesichert.

- **SHA256 Evidence:** Jede Datei-Aenderung wird mit SHA256-Hashes vor und nach dem Schreibvorgang dokumentiert
- **PQC Module:** Post-Quantum-Kryptografie mit Kyber und Dilithium Standards
- **Beweispfad:** `21_post_quantum_crypto/`
- **Garantie:** Quantencomputer-resistente Sicherheit fuer alle kryptografischen Operationen

---

## Saeule 5: CI/CD + Registry

**Prinzip:** Automatisierte Qualitaetssicherung und Agent-Verwaltung.

- **23 Workflows:** Automatisierte Build-, Test- und Deployment-Pipelines
- **Agent Registry:** Zentrale Verwaltung aller System-Agenten und ihrer Berechtigungen
- **Beweispfad:** `.github/workflows/`
- **Garantie:** Kein Code erreicht main ohne automatisierte Pruefung

---

## Saeule 6: Audit + Beweis (WORM Evidence)

**Prinzip:** Jede Systemaktion erzeugt einen unveraenderlichen Beweiseintrag.

- **WORM Evidence:** Write Once, Read Many -- 19882 Eintraege im Audit-System
- **Evidence-Logs:** Strukturierte JSON-Eintraege mit Zeitstempel, Agent-ID und SHA256-Hashes
- **Beweispfad:** `02_audit_logging/`
- **Garantie:** Lueckenlose Nachvollziehbarkeit aller Systemaktionen

---

## Saeule 7: Governance + Recht

**Prinzip:** Compliance und Governance sind im System kodifiziert, nicht nur dokumentiert.

- **13 Rego Policies:** Maschinenlesbare Governance-Regeln in Open Policy Agent (OPA)
- **Compliance-Framework:** DSGVO, ePrivacy, EU AI Act Konformitaet
- **Beweispfad:** `23_compliance/policies/`
- **Garantie:** Policy-Violations werden automatisch erkannt und blockiert

---

## Saeule 8: Selbstanpassung (TSAR Engine)

**Prinzip:** Das System kann sich selbst ueberwachen, analysieren und optimieren.

- **TSAR Engine:** Threat-Sensitive Adaptive Response -- automatische Reaktion auf Anomalien
- **Self-Healing:** Automatische Korrektur von erkannten Abweichungen
- **Beweispfad:** `24_meta_orchestration/tsar/`
- **Garantie:** Das System bleibt auch unter Angriff funktionsfaehig und integer

---

## Zusammenspiel der Saeulen

```
Wahrheit (1) --> definiert --> Struktur (2)
Struktur (2) --> wird geschuetzt durch --> Kontrolle (3)
Kontrolle (3) --> nutzt --> Kryptografie (4)
Kryptografie (4) --> wird geprueft durch --> CI/CD (5)
CI/CD (5) --> erzeugt --> Audit-Beweise (6)
Audit-Beweise (6) --> validieren --> Governance (7)
Governance (7) --> steuert --> Selbstanpassung (8)
Selbstanpassung (8) --> ueberwacht --> Wahrheit (1)
```

Jede Saeule staerkt die naechste. Der Kreislauf schliesst sich.

---

**Dieses Manifest ist kanonisch. Aenderungen erfordern L0-Freigabe.**
