# SSID Phase 1 — Root Module Matrix

## Objective
Prüfe und dokumentiere für alle 24 Roots die Common-MUST-Basis sowie den aktuellen Scaffold-/Baseline-Status.

## Common MUST je Root
- `module.yaml`
- `README.md`
- `docs/`
- `src/`
- `tests/`

## Pflichtspalten
| Root | Common MUST vorhanden | 16 Shards vorhanden | chart.yaml vorhanden | manifest strategy geklärt | tests baseline | taskspec status | Befund |
|---|---|---|---|---|---|---|---|

## Erwartete Root-Liste
01_ai_layer  
02_audit_logging  
03_core  
04_deployment  
05_documentation  
06_data_pipeline  
07_governance_legal  
08_identity_score  
09_meta_identity  
10_interoperability  
11_test_simulation  
12_tooling  
13_ui_layer  
14_zero_time_auth  
15_infra  
16_codex  
17_observability  
18_data_layer  
19_adapters  
20_foundation  
21_post_quantum_crypto  
22_datasets  
23_compliance  
24_meta_orchestration

## Bewertungslogik
- PASS: Common MUST vollständig, Shards vollständig, keine Semantikverletzung
- PARTIAL: Struktur vorhanden, aber dokumentierte Lücken in Charts/Tests/TaskSpecs
- FAIL: Root-Basis fehlt oder Root-/Registry-Policy verletzt

## Pflichtkommentar je FAIL/PARTIAL
- exakter Pfad
- Art des Mangels
- SAFE-FIX-konformer Reparaturpfad
- Evidence-Referenz
