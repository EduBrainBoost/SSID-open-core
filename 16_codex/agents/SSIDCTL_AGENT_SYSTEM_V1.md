# SSIDCTL Agent System v1 — 87-Agenten-Registry

Lesbare Spiegelung der operativen SoT-Quelle:
`24_meta_orchestration/registry/ssidctl_agent_registry.v1.json`

## Systemstruktur

| Ebene | Anzahl | Zweck |
|-------|--------|-------|
| L0 | 1 | Gesamtsteuerung |
| L1 | 5 | Repo-Verantwortung |
| L2 | 24 | Root-Verantwortung |
| L3 | 16 | Shard-/Domaenen-Verantwortung |
| L4 | 24 | Plattform-, Gate-, Audit-, Runtime-Spezialisten |
| L5 | 17 | Produkt-, Security-, Protocol-, Operations-Spezialisten |
| **Summe** | **87** | vollstaendiger SSIDCTL-Arbeitsverbund |

## Versionierung

| System | Status | Quelle |
|--------|--------|--------|
| legacy_v1 (29 Agents) | FROZEN | `24_meta_orchestration/agents/claude/agents_manifest.json` |
| ssidctl_v2 (87 Agents) | ACTIVE | `24_meta_orchestration/registry/ssidctl_agent_registry.v1.json` |

Kein Ueberschreiben des 29er Systems. Parallele Materialisierung mit kontrollierter Umschaltung.

## L0 — Gesamtsteuerung (1)

| Agent ID | Zweck |
|----------|-------|
| ssidctl.l0.master_orchestrator | Chief Supervisor, Gate-Freigabe, Konfliktaufloesung, Finalentscheid |

## L1 — Repo-Agents (5)

| Agent ID | Repo | Zweck |
|----------|------|-------|
| ssidctl.l1.repo_ssid | SSID | Hauptrepo-Steuerung, Root-24 Control |
| ssidctl.l1.repo_ems | SSID-EMS | EMS Portal, Backend, Console |
| ssidctl.l1.repo_orchestrator | SSID-orchestrator | Dispatcher, Worker, Provider |
| ssidctl.l1.repo_open_core | SSID-open-core | Public/Private Trennung, SDK |
| ssidctl.l1.repo_docs | SSID-docs | Dokumentation, Status, Handbuecher |

## L2 — Root-Agents (24)

| Agent ID | Root | Zweck |
|----------|------|-------|
| ssidctl.l2.01_ai_layer | 01_ai_layer | AI/Scoring/Explainability |
| ssidctl.l2.02_audit_logging | 02_audit_logging | Evidence/WORM/Hash-Ketten |
| ssidctl.l2.03_core | 03_core | Kernlogik/Resolver/Fee-Engine |
| ssidctl.l2.04_deployment | 04_deployment | Release-Gates/Rollout |
| ssidctl.l2.05_documentation | 05_documentation | Docs/Runbooks/Phase-Berichte |
| ssidctl.l2.06_data_pipeline | 06_data_pipeline | Event-/Datenpipelines |
| ssidctl.l2.07_governance_legal | 07_governance_legal | Governance/Regulatorik |
| ssidctl.l2.08_identity_score | 08_identity_score | Trust-Scoring |
| ssidctl.l2.09_meta_identity | 09_meta_identity | DID/VC-Kernmodelle |
| ssidctl.l2.10_interoperability | 10_interoperability | Protokollbruecken/Resolver |
| ssidctl.l2.11_test_simulation | 11_test_simulation | Tests/Simulation/Chaos |
| ssidctl.l2.12_tooling | 12_tooling | CLIs/Scripts/Automation |
| ssidctl.l2.13_ui_layer | 13_ui_layer | Produktoberflaechen/UX |
| ssidctl.l2.14_zero_time_auth | 14_zero_time_auth | WebAuthn/Auth-Flows |
| ssidctl.l2.15_infra | 15_infra | Secrets/Infra/Runtime |
| ssidctl.l2.16_codex | 16_codex | SoT/Master-Definition |
| ssidctl.l2.17_observability | 17_observability | Logs/Metrics/Tracing |
| ssidctl.l2.18_data_layer | 18_data_layer | Datenhaltung/Encryption |
| ssidctl.l2.19_adapters | 19_adapters | Externe Adapter/Provider |
| ssidctl.l2.20_foundation | 20_foundation | Token/Governance-Bausteine |
| ssidctl.l2.21_post_quantum_crypto | 21_post_quantum_crypto | PQC-Migration/Krypto |
| ssidctl.l2.22_datasets | 22_datasets | Dataset-Kataloge/Hashes |
| ssidctl.l2.23_compliance | 23_compliance | Policy-Engine/Nachweise |
| ssidctl.l2.24_meta_orchestration | 24_meta_orchestration | Registry/Locks/Orchestrierung |

## L3 — Shard-Agents (16)

| Agent ID | Shard | Domaene |
|----------|-------|---------|
| ssidctl.l3.shard_01_identitaet_personen | 01 | Personen-SSI |
| ssidctl.l3.shard_02_dokumente_nachweise | 02 | Dokumente/Nachweise |
| ssidctl.l3.shard_03_zugang_berechtigungen | 03 | Zugang/Berechtigungen |
| ssidctl.l3.shard_04_kommunikation_daten | 04 | Kommunikation/Daten |
| ssidctl.l3.shard_05_gesundheit_medizin | 05 | Gesundheit |
| ssidctl.l3.shard_06_bildung_qualifikationen | 06 | Bildung/Qualifikation |
| ssidctl.l3.shard_07_familie_soziales | 07 | Familie/Soziales |
| ssidctl.l3.shard_08_mobilitaet_fahrzeuge | 08 | Mobilitaet/Fahrzeuge |
| ssidctl.l3.shard_09_arbeit_karriere | 09 | Arbeit/Karriere |
| ssidctl.l3.shard_10_finanzen_banking | 10 | Finanzen/Banking |
| ssidctl.l3.shard_11_versicherungen_risiken | 11 | Versicherungen/Risiken |
| ssidctl.l3.shard_12_immobilien_grundstuecke | 12 | Immobilien |
| ssidctl.l3.shard_13_unternehmen_gewerbe | 13 | Unternehmen/KYB |
| ssidctl.l3.shard_14_vertraege_vereinbarungen | 14 | Vertraege |
| ssidctl.l3.shard_15_handel_transaktionen | 15 | Handel/Transaktionen |
| ssidctl.l3.shard_16_behoerden_verwaltung | 16 | Behoerden/eGov |

## L4 — Plattform-Spezialisten (24)

| Agent ID | Funktion |
|----------|----------|
| ssidctl.l4.branch_lock_manager | Branch-/Concurrency-Locks |
| ssidctl.l4.worktree_manager | Worktree-Steuerung |
| ssidctl.l4.prompt_compiler | Prompt-Aufbereitung |
| ssidctl.l4.task_router | Task-Routing |
| ssidctl.l4.state_registry_keeper | Registry-/State-Konsistenz |
| ssidctl.l4.contract_guard | Contract-/Schema-Schutz |
| ssidctl.l4.policy_enforcer | Policy-Enforcement |
| ssidctl.l4.structure_guardian | ROOT-24-Lock/Pfadschutz |
| ssidctl.l4.test_orchestrator | Testkoordination |
| ssidctl.l4.ci_gatekeeper | CI-Gates |
| ssidctl.l4.evidence_sealer | Evidence-Versiegelung |
| ssidctl.l4.hash_chain_auditor | Hash-Integritaet |
| ssidctl.l4.secret_sentinel | Secret-Schutz |
| ssidctl.l4.config_sanitizer | Config-Hygiene |
| ssidctl.l4.provider_failover_manager | Provider-Failover |
| ssidctl.l4.worker_resolver | Worker-Aufloesung |
| ssidctl.l4.sandbox_controller | Sandbox-Steuerung |
| ssidctl.l4.release_readiness_board | Readiness-Bewertung |
| ssidctl.l4.remediation_planner | Fehlerbehebung |
| ssidctl.l4.diff_forensics_analyst | Diff-/Forensik-Analyse |
| ssidctl.l4.salvage_coordinator | Salvage-Steuerung |
| ssidctl.l4.docs_normalizer | Doku-Normalisierung |
| ssidctl.l4.dependency_curator | Dependency-Kontrolle |
| ssidctl.l4.metrics_collector | Metrik-Sammlung |

## L5 — Produkt-Spezialisten (17)

| Agent ID | Funktion |
|----------|----------|
| ssidctl.l5.did_method_engineer | DID Method (did:ssid) |
| ssidctl.l5.vc_issuer_engineer | VC Issuance |
| ssidctl.l5.vc_verifier_engineer | VC Verification |
| ssidctl.l5.wallet_runtime_engineer | Wallet Runtime (non-custodial) |
| ssidctl.l5.webauthn_binding_engineer | WebAuthn/DID-Binding |
| ssidctl.l5.policy_mapping_analyst | Regulatorik-Mapping |
| ssidctl.l5.tokenomics_contract_engineer | Tokenomics/Fee-Logik |
| ssidctl.l5.dao_governance_engineer | DAO/Governance |
| ssidctl.l5.pqc_migration_engineer | Post-Quantum Migration |
| ssidctl.l5.adapter_integration_engineer | Externe Integrationen |
| ssidctl.l5.ems_console_runtime_engineer | EMS Console Runtime |
| ssidctl.l5.orchestrator_server_engineer | Orchestrator Server |
| ssidctl.l5.open_core_packager | Open-Core Packaging |
| ssidctl.l5.docs_site_publisher | Docs Publishing |
| ssidctl.l5.incident_response_operator | Incident Response |
| ssidctl.l5.chaos_rehearsal_operator | Chaos/Recovery |
| ssidctl.l5.compliance_evidence_clerk | Compliance Evidence |

## Activation Profiles

| Profil | Beschreibung |
|--------|-------------|
| gate55_core_11 | 11er Fuehrungsverbund Gate 5.5 + Phase 6 |
| full_87 | Vollstaendiger 87-Agenten-Verbund |
| ems_runtime_only | Nur EMS-relevante Agents |
| identity_core_phase6 | DID/VC/Wallet/Auth Produktkern |
| docs_registry_only | Docs + Registry Pflege |
| security_audit | Security-/Compliance-Audit |
| orchestrator_runtime_only | Nur Orchestrator |
| forensic_salvage | Forensik + kontrollierte Delta-Uebernahme |
| legacy_29_compat | Alt-System-Kompatibilitaet |

## Globale Regeln

- `workspace_root`: `C:\Users\bibel\SSID-Workspace\SSID-Arbeitsbereich\Github`
- `canonical_reference_only`: `C:\Users\bibel\Documents\Github` (keine KI-Schreibarbeit)
- `canonical_write`: **false**
- `mode`: LOCAL_FIRST, SAFE_FIX, ROOT_24_LOCK, NON_INTERACTIVE
- Jeder Agent: `can_touch_canonical: false`
- Koordination: ein Agent = ein Scope = keine Ueberschneidung ohne Lock
- Evidence: jeder Lauf mit UTC ISO8601 + SHA256

## Legacy-Mapping

29 bestehende Agenten bleiben erhalten. Mapping in:
`24_meta_orchestration/registry/ssidctl_legacy_mapping.v1.json`

Umschaltung erst nach:
1. Alle Tests PASS
2. Schema-Validierung PASS
3. Runtime-Loader bereit
4. Explizite Freigabe
