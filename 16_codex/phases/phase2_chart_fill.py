"""
Phase 2 Chart-Fill Script
Ergaenzt alle chart.yaml mit fehlenden Phase-2-Pflichtfeldern.
Quelle: Tier-0-SoT (Master Definition, Level-3-Struktur)
Modus: SAFE-FIX (additiv, kein Ueberschreiben bestehender Felder)
"""

import hashlib
import json
import os
from datetime import UTC, datetime

SSID_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT_DESCRIPTIONS = {
    "01_ai_layer": {
        "name": "AI/ML & Intelligenz",
        "purpose": "KI-Modelle, Risk/Trust-Scoring, Bias-/Fairness-Kontrollen, AI Governance (EU AI Act)",
    },
    "02_audit_logging": {
        "name": "Nachweise & Beweisfuehrung",
        "purpose": "Hash-Ledger, Evidence-Matrix, Blockchain Anchors, Audit-Trails, Retention",
    },
    "03_core": {
        "name": "Zentrale Logik",
        "purpose": "Smart Contract Kernsystem, Dispatcher, Identity-Resolver, Root-24-LOCK Enforcement",
    },
    "04_deployment": {
        "name": "Auslieferung & Distribution",
        "purpose": "CI/CD-Pipelines, Rollouts, Container, K8s, Terraform",
    },
    "05_documentation": {
        "name": "Dokumentation & I18N",
        "purpose": "Developer Guides, API Docs, Mehrsprachigkeit, Docusaurus",
    },
    "06_data_pipeline": {
        "name": "Datenfluss & Verarbeitung",
        "purpose": "ETL/ELT-Prozesse, Batch/Stream/Realtime, ML/AI Data-Feeds",
    },
    "07_governance_legal": {"name": "Recht & Steuerung", "purpose": "eIDAS, MiCA, DSGVO, DORA, DAO-Governance-Regeln"},
    "08_identity_score": {
        "name": "Reputation & Scoring",
        "purpose": "Identity Trust Levels, Scoring-Algorithmen, Verhaltensanalysen (hash-only)",
    },
    "09_meta_identity": {
        "name": "Digitale Identitaet",
        "purpose": "DID-Schemas, Identity Wallets, Selective Disclosure, Lifecycle",
    },
    "10_interoperability": {
        "name": "Kompatibilitaet",
        "purpose": "DID-Resolver, Cross-Chain Bridges, Protokoll-Adapter, API-Gateways",
    },
    "11_test_simulation": {
        "name": "Simulation & QA",
        "purpose": "Testumgebungen, Mock-Chains, Chaos Engineering, Benchmarking",
    },
    "12_tooling": {"name": "Werkzeuge", "purpose": "CLI, SDKs, CI-Helper, Linter, Automation Scripts"},
    "13_ui_layer": {
        "name": "Benutzeroberflaeche",
        "purpose": "Frontend, Dashboards, Partner-/User-Portale, Admin-GUIs",
    },
    "14_zero_time_auth": {
        "name": "Sofort-Authentifizierung",
        "purpose": "Real-Time KYC/KYB, Zero-Time Login, Biometrie, MFA, DID-Sessions",
    },
    "15_infra": {"name": "Infrastruktur", "purpose": "Cloud, Bare-Metal, Storage, Compute, Secrets/Key Management"},
    "16_codex": {"name": "Wissensbasis & Regeln", "purpose": "Codex, Policies, Blaupausen, SSID-Bibeln, SoT-Dokumente"},
    "17_observability": {"name": "Monitoring & Insights", "purpose": "Logging, Metrics, Tracing, Alerts, SIEM, AI-Ops"},
    "18_data_layer": {
        "name": "Datenhaltung",
        "purpose": "Datenbanken, GraphDBs, Time-Series, Encryption-at-Rest, Backups",
    },
    "19_adapters": {
        "name": "Anschluesse & Schnittstellen",
        "purpose": "Adapter zu externen APIs/Chains, Payment-Provider, Identity SDKs",
    },
    "20_foundation": {
        "name": "Grundlagen & Tokenomics",
        "purpose": "SSID-Token, Tokenomics, Distribution, NFT-Lizenzen, DAO-Treasury",
    },
    "21_post_quantum_crypto": {
        "name": "Zukunftskrypto",
        "purpose": "PQC-Algorithmen (Kyber, Dilithium), Quantum-Safe Migration",
    },
    "22_datasets": {"name": "Datenbestaende", "purpose": "Public Datasets, Hash-Referenzen, Zugriff via DID & Consent"},
    "23_compliance": {"name": "Regeltreue", "purpose": "AML, KYC, GDPR, Sanctions, Jurisdiktionsregeln, Evidence"},
    "24_meta_orchestration": {
        "name": "Zentrale Steuerung",
        "purpose": "Dispatcher, Registry, Locks, Trigger, Gates, Global Hash-Ledger",
    },
}

SHARD_DESCRIPTIONS = {
    "01_identitaet_personen": {
        "name": "Identitaet & Personen",
        "scope": "DIDs, Ausweise, Profile, Authentifizierung, Personen, Firmen, Organisationen",
    },
    "02_dokumente_nachweise": {
        "name": "Dokumente & Nachweise",
        "scope": "Urkunden, Bescheinigungen, Zertifikate, Vollmachten, digitale Signaturen",
    },
    "03_zugang_berechtigungen": {
        "name": "Zugang & Berechtigungen",
        "scope": "Rollen, Rechte, Mandanten, Delegationen, MFA, Zero-Trust, Sessions",
    },
    "04_kommunikation_daten": {
        "name": "Kommunikation & Daten",
        "scope": "Nachrichten, E-Mail, Chat, Datenaustausch, APIs, Benachrichtigungen",
    },
    "05_gesundheit_medizin": {
        "name": "Gesundheit & Medizin",
        "scope": "Krankenakte, Rezepte, Impfpass, Behandlungen, Kliniken, Apotheken",
    },
    "06_bildung_qualifikationen": {
        "name": "Bildung & Qualifikationen",
        "scope": "Zeugnisse, Abschluesse, Kurse, Weiterbildung, Zertifizierungen",
    },
    "07_familie_soziales": {
        "name": "Familie & Soziales",
        "scope": "Geburt, Heirat, Scheidung, Erbe, Vormundschaft, Sozialleistungen, Vereine",
    },
    "08_mobilitaet_fahrzeuge": {
        "name": "Mobilitaet & Fahrzeuge",
        "scope": "Fuehrerschein, KFZ-Zulassung, Fahrzeugpapiere, Maut, Versicherung",
    },
    "09_arbeit_karriere": {
        "name": "Arbeit & Karriere",
        "scope": "Arbeitsvertraege, Gehalt, Bewerbungen, Referenzen, Freelancing",
    },
    "10_finanzen_banking": {
        "name": "Finanzen & Banking",
        "scope": "Konten, Zahlungen, Kredite, Investments, DeFi, Krypto, Abonnements",
    },
    "11_versicherungen_risiken": {
        "name": "Versicherungen & Risiken",
        "scope": "Alle Versicherungsarten, Schaeden, Claims, Policen, Praemien",
    },
    "12_immobilien_grundstuecke": {
        "name": "Immobilien & Grundstuecke",
        "scope": "Eigentum, Miete, Pacht, Grundbuch, Hypotheken, Bewertungen",
    },
    "13_unternehmen_gewerbe": {
        "name": "Unternehmen & Gewerbe",
        "scope": "Firmendaten, Handelsregister, Lizenzen, B2B, Buchhaltung, Bilanzen",
    },
    "14_vertraege_vereinbarungen": {
        "name": "Vertraege & Vereinbarungen",
        "scope": "Smart Contracts, Geschaeftsvertraege, AGBs, SLAs, Partnerschaften",
    },
    "15_handel_transaktionen": {
        "name": "Handel & Transaktionen",
        "scope": "Kaeufe, Verkaeufe, Rechnungen, Garantien, Supply Chain, Logistik",
    },
    "16_behoerden_verwaltung": {
        "name": "Behoerden & Verwaltung",
        "scope": "Aemter, Antraege, Genehmigungen, Steuern, Meldewesen, Gerichtsurteile",
    },
}

GOVERNANCE_TEMPLATE = """
governance:
  change_process: "RFC required for capability changes, dual review for policy changes"
  dual_review:
    architecture: architecture_board
    compliance: compliance_board
  semver_rule: "MAJOR for breaking changes, MINOR for new capabilities, PATCH for fixes"
  promotion_rule: "G-workspace validated, then promoted to C via git_promotion_guard"
  rollback_rule: "Snapshot before promotion, restore on failure with evidence"
"""

EVIDENCE_TEMPLATE = """
evidence_strategy:
  events:
    - "chart_change"
    - "manifest_change"
    - "implementation_change"
    - "test_result"
    - "promotion_event"
  storage_path: "23_compliance/evidence/{root_id}/"
  retention: "10 years (WORM-eligible)"
  anchoring: "SHA256 hash chain, optional blockchain anchor"
  audit_owner: "02_audit_logging"
"""

OBSERVABILITY_TEMPLATE = """
observability:
  metrics: "17_observability/metrics/{root_id}.yaml"
  logs: "17_observability/logs/{root_id}/"
  traces: "distributed tracing via OpenTelemetry"
  alerts: "17_observability/alerts/{root_id}.yaml"
  health_checks: "liveness and readiness probes required"
"""

TESTING_TEMPLATE = """
testing:
  unit: "tests/unit/"
  integration: "tests/integration/"
  contract: "conformance tests against OpenAPI/JSON-Schema"
  conformance: "conformance/"
  performance: "load tests via locust"
  security: "SAST/DAST scans, dependency audit"
"""

IMPLEMENTATION_HANDOFF_TEMPLATE = """
implementation_handoff:
  allowed_impl_types:
    - "python"
    - "typescript"
    - "solidity"
    - "rust"
  manifest_preconditions:
    - "chart.yaml at COMPLETE_SOT"
    - "contracts/schemas defined"
    - "tests skeleton present"
  tech_constraints:
    - "hash-only data model"
    - "non-custodial architecture"
    - "no PII storage"
"""

RELEASE_TEMPLATE = """
release:
  maturity: "draft"
  blockers:
    - "chart-fill incomplete"
    - "no real implementation"
  exit_criteria:
    - "all MUST capabilities implemented"
    - "unit + integration tests green"
    - "evidence trail complete"
    - "promotion gate passed"
  documentation_targets:
    - "API docs"
    - "developer guide"
    - "compliance mapping"
"""


def add_missing_fields(chart_path, root_id, shard_id):
    """Add missing Phase-2 fields to a chart.yaml (SAFE-FIX: additive only)."""
    with open(chart_path, encoding="utf-8") as f:
        content = f.read()

    original_hash = hashlib.sha256(content.encode()).hexdigest()

    # Parse existing top-level keys
    existing_keys = set()
    for line in content.split("\n"):
        stripped = line.strip()
        if (
            ":" in stripped
            and not stripped.startswith("-")
            and not stripped.startswith("#")
            and not line.startswith(" ")
            and not line.startswith("\t")
        ):
            key = stripped.split(":")[0].strip()
            existing_keys.add(key)

    root_info = ROOT_DESCRIPTIONS.get(root_id, {"name": root_id, "purpose": "See Tier-0 SoT"})
    shard_info = SHARD_DESCRIPTIONS.get(shard_id, {"name": shard_id, "scope": "See Tier-0 SoT"})

    additions = []

    if "root_name" not in existing_keys:
        additions.append(f'root_name: "{root_info["name"]}"')
    if "shard_name" not in existing_keys and "title" not in existing_keys:
        additions.append(f'shard_name: "{shard_info["name"]}"')
    if "purpose" not in existing_keys:
        additions.append(f'purpose: "{root_info["purpose"]} fuer {shard_info["name"]}"')
    if "scope" not in existing_keys:
        additions.append(f'scope: "{shard_info["scope"]}"')
    if "responsibilities" not in existing_keys:
        additions.append(
            f'responsibilities:\n  - "Fachliche SoT-Beschreibung fuer {root_info["name"]} im Kontext {shard_info["name"]}"'
        )
    if "dependencies" not in existing_keys:
        additions.append(
            'dependencies:\n  - "03_core (zentrale Logik)"\n  - "23_compliance (Regeltreue)"\n  - "24_meta_orchestration (Registry)"'
        )
    if "governance" not in existing_keys:
        additions.append(GOVERNANCE_TEMPLATE.strip())
    if "evidence_strategy" not in existing_keys and "evidence" not in existing_keys:
        additions.append(EVIDENCE_TEMPLATE.strip().replace("{root_id}", root_id))
    if "observability" not in existing_keys:
        additions.append(OBSERVABILITY_TEMPLATE.strip().replace("{root_id}", root_id))
    if "testing" not in existing_keys:
        additions.append(TESTING_TEMPLATE.strip())
    if "implementation_handoff" not in existing_keys:
        additions.append(IMPLEMENTATION_HANDOFF_TEMPLATE.strip())
    if "release" not in existing_keys:
        additions.append(RELEASE_TEMPLATE.strip())
    if "maturity" not in existing_keys:
        additions.append('maturity: "draft"')
    if "promotion_rules" not in existing_keys:
        if "governance" in existing_keys:
            pass  # promotion_rules may be nested under governance
        else:
            additions.append(
                'promotion_rules:\n  - "G-workspace validation required"\n  - "Dual review (architecture + compliance)"\n  - "Evidence trail complete"\n  - "All MUST tests green"'
            )
    if "exclusions" not in existing_keys:
        additions.append(
            'exclusions:\n  - "No PII storage"\n  - "No custodial operations"\n  - "No mainnet deployment without audit"'
        )
    if "sot_sources" not in existing_keys:
        additions.append(
            'sot_sources:\n  - "16_codex/ssid_master_definition_corrected_v1.1.1.md"\n  - "16_codex/SSID_structure_level3_part1_MAX.md"\n  - "16_codex/SSID_structure_level3_part2_MAX.md"\n  - "16_codex/SSID_structure_level3_part3_MAX.md"'
        )
    if "owner" not in existing_keys:
        additions.append('owner: "SSID Architecture Board"')
    if "last_reviewed_at" not in existing_keys:
        additions.append(f'last_reviewed_at: "{datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}"')

    if not additions:
        return None  # Nothing to add

    new_content = content.rstrip() + "\n\n# --- Phase 2 Chart-Fill (auto-generated from Tier-0 SoT) ---\n"
    for addition in additions:
        new_content += addition + "\n"
    new_content += "\n"

    new_hash = hashlib.sha256(new_content.encode()).hexdigest()

    with open(chart_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return {"sha256_before": original_hash, "sha256_after": new_hash, "fields_added": len(additions)}


def main():
    roots = sorted(
        [d for d in os.listdir(SSID_ROOT) if os.path.isdir(os.path.join(SSID_ROOT, d)) and d[:2].isdigit() and "_" in d]
    )

    canonical_shards = [
        "01_identitaet_personen",
        "02_dokumente_nachweise",
        "03_zugang_berechtigungen",
        "04_kommunikation_daten",
        "05_gesundheit_medizin",
        "06_bildung_qualifikationen",
        "07_familie_soziales",
        "08_mobilitaet_fahrzeuge",
        "09_arbeit_karriere",
        "10_finanzen_banking",
        "11_versicherungen_risiken",
        "12_immobilien_grundstuecke",
        "13_unternehmen_gewerbe",
        "14_vertraege_vereinbarungen",
        "15_handel_transaktionen",
        "16_behoerden_verwaltung",
    ]

    results = {"updated": 0, "skipped": 0, "errors": 0, "total_fields_added": 0}
    evidence = []

    for root in roots:
        shards_dir = os.path.join(SSID_ROOT, root, "shards")
        if not os.path.isdir(shards_dir):
            continue
        for shard in sorted(os.listdir(shards_dir)):
            if shard not in canonical_shards:
                continue  # Skip anomalies like 17_iot_geraete
            chart_path = os.path.join(shards_dir, shard, "chart.yaml")
            if not os.path.isfile(chart_path):
                results["errors"] += 1
                continue
            try:
                result = add_missing_fields(chart_path, root, shard)
                if result:
                    results["updated"] += 1
                    results["total_fields_added"] += result["fields_added"]
                    evidence.append(
                        {
                            "root": root,
                            "shard": shard,
                            "sha256_before": result["sha256_before"],
                            "sha256_after": result["sha256_after"],
                            "fields_added": result["fields_added"],
                        }
                    )
                else:
                    results["skipped"] += 1
            except Exception as e:
                results["errors"] += 1
                print(f"ERROR: {root}/{shard}: {e}")

    print(json.dumps(results, indent=2))

    # Write evidence
    evidence_path = os.path.join(SSID_ROOT, "23_compliance", "evidence", "phase2", "phase2_chart_fill_evidence.json")
    os.makedirs(os.path.dirname(evidence_path), exist_ok=True)
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "phase": 2,
                "operation": "chart_fill",
                "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": results,
                "entries_count": len(evidence),
                "first_10_entries": evidence[:10],
            },
            f,
            indent=2,
        )

    print(f"\nEvidence written to: {evidence_path}")


if __name__ == "__main__":
    main()
