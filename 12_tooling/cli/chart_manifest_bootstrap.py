#!/usr/bin/env python3
"""Bootstrap missing root, shard, chart, manifest, TaskSpec, and audit assets."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from _lib.shards import ROOTS_24, SHARDS_16, find_roots, parse_yaml, write_yaml
from shard_manifest_build import generate_manifest
from shards_registry_build import build_registry

REPORT_RELATIVE_PATH = Path("02_audit_logging/reports/CHART_MANIFEST_BOOTSTRAP_REPORT.json")
AGENT_RUN_RELATIVE_PATH = Path("02_audit_logging/agent_runs/AI_CLI_INTEGRATION_LOG.jsonl")
REGISTRY_RELATIVE_PATH = Path("24_meta_orchestration/registry/shards_registry.json")
TASKSPEC_DIR_RELATIVE_PATH = Path("24_meta_orchestration/registry")

ROOT_METADATA: dict[str, dict[str, str]] = {
    "01_ai_layer": {"name": "AI Layer", "classification": "AI Orchestration", "purpose": "ai_orchestration"},
    "02_audit_logging": {"name": "Audit Logging", "classification": "Audit Logging", "purpose": "audit_logging"},
    "03_core": {
        "name": "Core Validators & Authority",
        "classification": "Internal Authority",
        "purpose": "final_authority",
    },
    "04_deployment": {"name": "Deployment", "classification": "Deployment", "purpose": "deployment"},
    "05_documentation": {"name": "Documentation", "classification": "Documentation", "purpose": "documentation"},
    "06_data_pipeline": {"name": "Data Pipeline", "classification": "Data Pipeline", "purpose": "data_pipeline"},
    "07_governance_legal": {"name": "Governance Legal", "classification": "Governance", "purpose": "governance_legal"},
    "08_identity_score": {"name": "Identity Score", "classification": "Scoring", "purpose": "identity_scoring"},
    "09_meta_identity": {"name": "Meta Identity", "classification": "Identity Metadata", "purpose": "meta_identity"},
    "10_interoperability": {"name": "Interoperability", "classification": "Integration", "purpose": "interoperability"},
    "11_test_simulation": {
        "name": "Test Simulation",
        "classification": "Quality Assurance",
        "purpose": "test_simulation",
    },
    "12_tooling": {
        "name": "Tooling & CLI Infrastructure",
        "classification": "Developer Tools",
        "purpose": "developer_tooling",
    },
    "13_ui_layer": {"name": "UI Layer", "classification": "User Interface", "purpose": "ui_layer"},
    "14_zero_time_auth": {"name": "Zero Time Auth", "classification": "Authentication", "purpose": "zero_time_auth"},
    "15_infra": {"name": "Infrastructure", "classification": "Infrastructure", "purpose": "infrastructure"},
    "16_codex": {"name": "Codex & Contracts", "classification": "Governance", "purpose": "codex_contracts"},
    "17_observability": {"name": "Observability", "classification": "Observability", "purpose": "observability"},
    "18_data_layer": {"name": "Data Layer", "classification": "Data Platform", "purpose": "data_layer"},
    "19_adapters": {"name": "Adapters", "classification": "Adapters", "purpose": "adapter_layer"},
    "20_foundation": {"name": "Foundation", "classification": "Foundation", "purpose": "foundation"},
    "21_post_quantum_crypto": {
        "name": "Post Quantum Crypto",
        "classification": "Cryptography",
        "purpose": "post_quantum_crypto",
    },
    "22_datasets": {"name": "Datasets", "classification": "Datasets", "purpose": "datasets"},
    "23_compliance": {"name": "Compliance", "classification": "Compliance", "purpose": "compliance"},
    "24_meta_orchestration": {
        "name": "Meta Orchestration",
        "classification": "Orchestration",
        "purpose": "workflow_orchestration",
    },
}

ROOT03_RUNTIME_SHARDS: dict[str, str] = {
    "01_identitaet_personen": "01_identitaet_personen",
    "02_dokumente_nachweise": "02_dokumente_nachweise",
    "03_shard_03": "03_verifiable_credentials",
    "04_shard_04": "04_did_resolution",
    "05_shard_05": "05_claims_binding",
}

ROOT09_RUNTIME_SHARDS: dict[str, str] = {
    "01_identitaet_personen": "01_identitaet_personen",
    "02_dokumente_nachweise": "02_dokumente_nachweise",
    "03_shard_03": "03_verifiable_credentials",
    "04_shard_04": "04_did_resolution",
    "05_shard_05": "05_claims_binding",
}

ROOT07_RUNTIME_SHARDS: dict[str, str] = {
    "01_identitaet_personen": "01_identitaet_personen",
    "02_dokumente_nachweise": "02_dokumente_nachweise",
    "03_shard_03": "03_verifiable_credentials",
    "04_shard_04": "04_did_resolution",
    "05_shard_05": "05_claims_binding",
}


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_text_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.replace("\r\n", "\n"), encoding="utf-8")
    return True


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def titleize(token: str) -> str:
    return " ".join(part.capitalize() for part in token.split("_"))


def build_module_descriptor(root_name: str) -> dict[str, Any]:
    meta = ROOT_METADATA[root_name]
    descriptor: dict[str, Any] = {
        "module_id": root_name,
        "name": meta["name"],
        "version": "4.1.0",
        "status": "ROOT-24-LOCK",
        "classification": meta["classification"],
        "purpose": meta["purpose"],
        "structure": {
            "must_dirs": ["docs", "src", "tests", "config", "shards"],
            "must_files": ["module.yaml", "README.md"],
            "forbidden_paths": ["compliance_policies", "audit_storage", "governance_rules"],
        },
        "interfaces": {
            "outputs": [{"ref": f"17_observability/logs/{root_name[3:]}", "type": "log_sink"}],
            "evidence": [{"ref": f"23_compliance/evidence/{root_name[3:]}", "type": "evidence_target"}],
        },
        "shard_count": len(SHARDS_16),
        "evidence_strategy": "hash_manifest_only",
        "governance_rules": ["SOT_AGENT_021", "SOT_AGENT_022", "SOT_AGENT_023"],
    }
    if root_name == "03_core":
        descriptor["delegates_from"] = "01_ai_layer"
    else:
        descriptor["final_authority"] = "03_core"
    return descriptor


def build_root_readme(root_name: str) -> str:
    meta = ROOT_METADATA[root_name]
    return (
        f"# {root_name} - {meta['name']}\n\n"
        f"**Classification:** {meta['classification']}\n"
        f"**SoT Version:** v4.1.0\n"
        f"**Status:** ROOT-24-LOCK\n\n"
        f"## Purpose\n\n"
        f"Bootstrap scaffold for {meta['name']} under the chart/manifest hydration baseline.\n"
    )


def build_chart(root_name: str, shard_name: str) -> dict[str, Any]:
    shard_title = titleize(shard_name[3:])
    chart: dict[str, Any] = {
        "schema_version": "1.0.0",
        "root_id": root_name,
        "shard_id": shard_name,
        "title": shard_title,
        "status": "active",
        "version": "0.1.0",
        "implementation_stage": "bootstrap_minimum",
        "interfaces": [
            {
                "id": "primary_interface",
                "ref": f"{root_name}/shards/{shard_name}/interfaces/interface.yaml",
            }
        ],
        "policies": [
            {
                "id": f"{root_name}.{shard_name}.baseline_policy",
                "ref": f"{root_name}/shards/{shard_name}/policies/policy.yaml",
            }
        ],
        "governance": {
            "rule_refs": ["ROOT-24-LOCK", "SAFE-FIX", "SOT_AGENT_021", "SOT_AGENT_022", "SOT_AGENT_023"],
            "ref": f"{root_name}/shards/{shard_name}/governance/rules.yaml",
        },
        "evidence_strategy": {
            "mode": "hash_manifest_only",
            "ref": f"{root_name}/shards/{shard_name}/evidence/strategy.yaml",
        },
        "contracts": {
            "mode": "contract_first",
            "paths": [
                f"{root_name}/shards/{shard_name}/contracts/inputs.schema.json",
                f"{root_name}/shards/{shard_name}/contracts/outputs.schema.json",
                f"{root_name}/shards/{shard_name}/contracts/events.schema.json",
            ],
        },
        "promotion_rules": {
            "defined": ["chart_present", "manifest_present"],
            "contract_ready": ["contracts_present", "fixtures_present"],
            "conformance_ready": ["gate_pass"],
        },
    }
    return chart


def write_yaml_force(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    content = content.replace("\r\n", "\n")
    path.write_bytes(content.encode("utf-8"))


def build_interface_template(root_name: str, shard_name: str) -> dict[str, Any]:
    return {
        "interface_id": f"{root_name}.{shard_name}.primary",
        "root_id": root_name,
        "shard_id": shard_name,
        "kind": "bootstrap_contract",
        "status": "active",
    }


def build_policy_template(root_name: str, shard_name: str) -> dict[str, Any]:
    return {
        "policy_id": f"{root_name}.{shard_name}.baseline_policy",
        "root_id": root_name,
        "shard_id": shard_name,
        "mode": "advisory",
        "enforcement": "fail_closed_on_missing_contracts",
    }


def build_governance_template(root_name: str, shard_name: str) -> dict[str, Any]:
    return {
        "root_id": root_name,
        "shard_id": shard_name,
        "rule_refs": ["ROOT-24-LOCK", "SAFE-FIX", "SOT_AGENT_021", "SOT_AGENT_022", "SOT_AGENT_023"],
    }


def build_evidence_template(root_name: str, shard_name: str) -> dict[str, Any]:
    return {
        "root_id": root_name,
        "shard_id": shard_name,
        "strategy": "hash_manifest_only",
        "target": f"23_compliance/evidence/{root_name[3:]}/{shard_name}",
    }


def build_contract_index(schema_filename: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "entries": [{"kind": "json_schema", "path": schema_filename}],
    }


def build_contracts_index(schema_names: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "entries": [{"kind": "json_schema", "path": schema_name} for schema_name in schema_names],
    }


def build_conformance_index() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "entries": [
            {"kind": "fixture", "path": "fixtures/fixture_valid.json"},
            {"kind": "fixture", "path": "fixtures/fixture_invalid.json"},
        ],
    }


def build_evidence_index() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "entries": [{"kind": "strategy", "path": "strategy.yaml"}],
    }


def build_runtime_index(shard_name: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "kind": "reference_runtime",
        "module": "wave03_reference",
        "factory": "Root03ReferenceWave",
        "service_method": "run",
        "shard_id": ROOT03_RUNTIME_SHARDS[shard_name],
        "valid_input": "../conformance/fixtures/fixture_valid.json",
        "expected_output_schema": "../contracts/outputs.schema.json",
    }


def build_service_runtime_index(shard_name: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "kind": "reference_service_runtime",
        "module": "wave09_identity_services",
        "factory": "Root09IdentityServicesWave",
        "service_method": "run",
        "shard_id": ROOT09_RUNTIME_SHARDS[shard_name],
        "valid_input": "../conformance/fixtures/fixture_valid.json",
        "expected_output_schema": "../contracts/outputs.schema.json",
        "dependency_refs": [f"03_core/{shard_name}"],
    }


def build_security_runtime_index(shard_name: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "kind": "reference_security_runtime",
        "module": "wave07_security_enforcement",
        "factory": "Root07SecurityEnforcementWave",
        "service_method": "run",
        "shard_id": ROOT07_RUNTIME_SHARDS[shard_name],
        "valid_input": "../conformance/fixtures/fixture_valid.json",
        "expected_output_schema": "../contracts/outputs.schema.json",
        "dependency_refs": [f"03_core/{shard_name}", f"09_meta_identity/{shard_name}"],
    }


def build_identity_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["proof_hash", "issuer_code"],
        "properties": {
            "proof_hash": {"type": "string", "minLength": 32},
            "issuer_code": {"type": "string", "minLength": 2},
        },
        "additionalProperties": False,
    }


def build_document_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["document_hash", "document_type"],
        "properties": {
            "document_hash": {"type": "string", "minLength": 32},
            "document_type": {"type": "string", "enum": ["credential", "attestation"]},
        },
        "additionalProperties": False,
    }


def build_valid_fixture(schema_kind: str) -> dict[str, Any]:
    if schema_kind == "identity":
        return {"proof_hash": "a" * 64, "issuer_code": "DE"}
    return {"document_hash": "b" * 64, "document_type": "credential"}


def build_invalid_fixture(schema_kind: str) -> dict[str, Any]:
    if schema_kind == "identity":
        return {"issuer_code": "DE"}
    return {"document_hash": "b" * 64, "document_type": "unsupported"}


def build_generic_schema(root_name: str, shard_name: str, schema_kind: str) -> dict[str, Any]:
    base_required = {
        "inputs": ["request_id", "payload_hash"],
        "outputs": ["result_id", "status"],
        "events": ["event_id", "event_type"],
    }[schema_kind]
    properties: dict[str, Any] = {
        "request_id": {"type": "string", "minLength": 8},
        "payload_hash": {"type": "string", "minLength": 32},
        "result_id": {"type": "string", "minLength": 8},
        "status": {"type": "string", "enum": ["accepted", "rejected"]},
        "event_id": {"type": "string", "minLength": 8},
        "event_type": {"type": "string", "enum": [f"{root_name}.{shard_name}.{schema_kind}"]},
    }
    selected = {key: value for key, value in properties.items() if key in base_required}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": base_required,
        "properties": selected,
        "additionalProperties": False,
    }


def build_valid_fixture_payload(root_name: str, shard_name: str, schema_kind: str) -> dict[str, Any]:
    if schema_kind == "inputs":
        return {"request_id": f"{root_name}-{shard_name}", "payload_hash": "a" * 64}
    if schema_kind == "outputs":
        return {"result_id": f"{root_name}-{shard_name}", "status": "accepted"}
    return {"event_id": f"{root_name}-{shard_name}", "event_type": f"{root_name}.{shard_name}.events"}


def build_invalid_fixture_payload(root_name: str, shard_name: str, schema_kind: str) -> dict[str, Any]:
    if schema_kind == "inputs":
        return {"request_id": f"{root_name}-{shard_name}"}
    if schema_kind == "outputs":
        return {"result_id": f"{root_name}-{shard_name}", "status": "unsupported"}
    return {"event_id": f"{root_name}-{shard_name}"}


def ensure_contract_pack(shard_dir: Path, root_name: str, shard_name: str, summary: dict[str, int]) -> None:
    contracts_dir = shard_dir / "contracts"
    conformance_dir = shard_dir / "conformance"
    fixtures_dir = conformance_dir / "fixtures"
    evidence_dir = shard_dir / "evidence"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    schema_names = ["inputs.schema.json", "outputs.schema.json", "events.schema.json"]
    for schema_name, schema_kind in zip(schema_names, ["inputs", "outputs", "events"], strict=False):
        schema_path = contracts_dir / schema_name
        schema_payload = build_generic_schema(root_name, shard_name, schema_kind)
        if write_text_if_missing(schema_path, json.dumps(schema_payload, indent=2, ensure_ascii=False) + "\n"):
            summary["contracts_created"] += 1
    if write_yaml(contracts_dir / "index.yaml", build_contracts_index(schema_names)):
        summary["indexes_created"] += 1
    if write_yaml(conformance_dir / "index.yaml", build_conformance_index()):
        summary["indexes_created"] += 1
    if write_yaml(evidence_dir / "index.yaml", build_evidence_index()):
        summary["indexes_created"] += 1
    if write_text_if_missing(
        fixtures_dir / "fixture_valid.json",
        json.dumps(build_valid_fixture_payload(root_name, shard_name, "inputs"), indent=2) + "\n",
    ):
        summary["fixtures_created"] += 1
    if write_text_if_missing(
        fixtures_dir / "fixture_invalid.json",
        json.dumps(build_invalid_fixture_payload(root_name, shard_name, "inputs"), indent=2) + "\n",
    ):
        summary["fixtures_created"] += 1
    if write_text_if_missing(
        shard_dir / "README.md",
        f"# {root_name}/{shard_name}\n\nCapability definition for deterministic shard contract baseline.\n",
    ):
        summary["readmes_created"] += 1


def ensure_pilot_contracts(root_dir: Path, shard_name: str, summary: dict[str, int]) -> None:
    shard_dir = root_dir / "shards" / shard_name
    contracts_dir = shard_dir / "contracts"
    fixtures_dir = shard_dir / "conformance" / "fixtures"
    evidence_dir = shard_dir / "evidence"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if shard_name == "01_identitaet_personen":
        schema_name = "identity_proof.schema.json"
        schema = build_identity_schema()
        schema_kind = "identity"
    else:
        schema_name = "document_proof.schema.json"
        schema = build_document_schema()
        schema_kind = "document"

    if write_text_if_missing(contracts_dir / schema_name, json.dumps(schema, indent=2, ensure_ascii=False) + "\n"):
        summary["contracts_created"] += 1
    if write_yaml(contracts_dir / "index.yaml", build_contract_index(schema_name)):
        summary["indexes_created"] += 1
    if write_yaml(shard_dir / "conformance" / "index.yaml", build_conformance_index()):
        summary["indexes_created"] += 1
    if write_yaml(evidence_dir / "index.yaml", build_evidence_index()):
        summary["indexes_created"] += 1
    if write_text_if_missing(
        fixtures_dir / "valid_identity.json", json.dumps(build_valid_fixture(schema_kind), indent=2) + "\n"
    ):
        summary["fixtures_created"] += 1
    if write_text_if_missing(
        fixtures_dir / "invalid_identity.json", json.dumps(build_invalid_fixture(schema_kind), indent=2) + "\n"
    ):
        summary["fixtures_created"] += 1
    if write_text_if_missing(
        shard_dir / "README.md", f"# 03_core/{shard_name}\n\nPilot shard contract and conformance definition.\n"
    ):
        summary["readmes_created"] += 1


def ensure_root_scaffold(repo_root: Path, root_name: str, summary: dict[str, int]) -> Path:
    root_dir = repo_root / root_name
    if not root_dir.exists():
        root_dir.mkdir(parents=True, exist_ok=True)
        summary["roots_created"] += 1
    for dirname in ["docs", "src", "tests", "config", "shards"]:
        target = root_dir / dirname
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            summary["directories_created"] += 1
    if write_yaml(root_dir / "module.yaml", build_module_descriptor(root_name)):
        summary["module_files_created"] += 1
    if write_text_if_missing(root_dir / "README.md", build_root_readme(root_name)):
        summary["readmes_created"] += 1
    return root_dir


def ensure_shard_assets(root_dir: Path, root_name: str, shard_name: str, summary: dict[str, int]) -> None:
    shard_dir = root_dir / "shards" / shard_name
    if not shard_dir.exists():
        shard_dir.mkdir(parents=True, exist_ok=True)
        summary["shards_created"] += 1
    for subdir in ["interfaces", "policies", "governance", "evidence"]:
        target = shard_dir / subdir
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            summary["directories_created"] += 1
    chart_path = shard_dir / "chart.yaml"
    chart_payload = build_chart(root_name, shard_name)
    if write_yaml(chart_path, chart_payload):
        summary["charts_created"] += 1
    else:
        write_yaml_force(chart_path, chart_payload)
    if write_yaml(shard_dir / "interfaces" / "interface.yaml", build_interface_template(root_name, shard_name)):
        summary["templates_created"] += 1
    if write_yaml(shard_dir / "policies" / "policy.yaml", build_policy_template(root_name, shard_name)):
        summary["templates_created"] += 1
    if write_yaml(shard_dir / "governance" / "rules.yaml", build_governance_template(root_name, shard_name)):
        summary["templates_created"] += 1
    if write_yaml(shard_dir / "evidence" / "strategy.yaml", build_evidence_template(root_name, shard_name)):
        summary["templates_created"] += 1
    if root_name == "03_core" and shard_name in ROOT03_RUNTIME_SHARDS:
        runtime_dir = shard_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        if write_yaml(runtime_dir / "index.yaml", build_runtime_index(shard_name)):
            summary["indexes_created"] += 1
    if root_name == "09_meta_identity" and shard_name in ROOT09_RUNTIME_SHARDS:
        runtime_dir = shard_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        if write_yaml(runtime_dir / "index.yaml", build_service_runtime_index(shard_name)):
            summary["indexes_created"] += 1
    if root_name == "07_governance_legal" and shard_name in ROOT07_RUNTIME_SHARDS:
        runtime_dir = shard_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        if write_yaml(runtime_dir / "index.yaml", build_security_runtime_index(shard_name)):
            summary["indexes_created"] += 1
    ensure_contract_pack(shard_dir, root_name, shard_name, summary)
    if root_name == "03_core" and shard_name in {"01_identitaet_personen", "02_dokumente_nachweise"}:
        ensure_pilot_contracts(root_dir, shard_name, summary)
    chart = yaml.safe_load(chart_path.read_text(encoding="utf-8"))
    if write_yaml(shard_dir / "manifest.yaml", generate_manifest(shard_dir, root_name, chart)):
        summary["manifests_created"] += 1


def build_registry_snapshot(repo_root: Path) -> dict[str, Any]:
    default_repo_root = Path(__file__).resolve().parents[2].resolve()
    repo_root = repo_root.resolve()
    if repo_root == default_repo_root:
        return build_registry(find_roots(repo_root), deterministic=True)

    shards: list[dict[str, Any]] = []
    for root_name in ROOTS_24:
        for shard_name in SHARDS_16:
            shard_dir = repo_root / root_name / "shards" / shard_name
            chart_path = shard_dir / "chart.yaml"
            manifest_path = shard_dir / "manifest.yaml"
            contracts_index = shard_dir / "contracts" / "index.yaml"
            conformance_index = shard_dir / "conformance" / "index.yaml"
            evidence_index = shard_dir / "evidence" / "index.yaml"
            runtime_index = shard_dir / "runtime" / "index.yaml"
            runtime_status = "ready" if runtime_index.exists() else "missing"
            runtime_spec = parse_yaml(runtime_index) if runtime_index.exists() else {}
            dependencies = list((runtime_spec or {}).get("dependency_refs", []) or [])
            dependency_status = "not_applicable"
            if dependencies:
                dependency_status = "ready"
                for dependency_ref in dependencies:
                    dep_root, dep_shard = str(dependency_ref).split("/", 1)
                    dep_runtime = repo_root / dep_root / "shards" / dep_shard / "runtime" / "index.yaml"
                    if not dep_runtime.exists():
                        dependency_status = "missing"
                        break
            status = "conformance_ready"
            if runtime_status == "ready":
                status = "runtime_ready"
            if dependency_status == "ready":
                status = "cross_root_runtime_ready"
            shards.append(
                {
                    "root_id": root_name,
                    "shard_id": shard_name,
                    "chart_path": chart_path.relative_to(repo_root).as_posix(),
                    "manifest_path": manifest_path.relative_to(repo_root).as_posix(),
                    "contracts_index_path": contracts_index.relative_to(repo_root).as_posix()
                    if contracts_index.exists()
                    else None,
                    "conformance_index_path": conformance_index.relative_to(repo_root).as_posix()
                    if conformance_index.exists()
                    else None,
                    "evidence_index_path": evidence_index.relative_to(repo_root).as_posix()
                    if evidence_index.exists()
                    else None,
                    "runtime_index_path": runtime_index.relative_to(repo_root).as_posix()
                    if runtime_index.exists()
                    else None,
                    "promotion_tier": "MUST"
                    if root_name == "03_core" and shard_name in {"01_identitaet_personen", "02_dokumente_nachweise"}
                    else "WARN",
                    "status": status,
                    "runtime_status": runtime_status,
                    "dependency_status": dependency_status,
                    "runtime_dependency_refs": dependencies,
                }
            )
    shards.sort(key=lambda entry: (entry["root_id"], entry["shard_id"]))
    return {
        "schema_version": "1.0.0",
        "generated_at_utc": utc_now(),
        "shard_count": len(shards),
        "shards": shards,
    }


def ensure_taskspecs(repo_root: Path, summary: dict[str, int]) -> None:
    registry_dir = repo_root / TASKSPEC_DIR_RELATIVE_PATH
    registry_dir.mkdir(parents=True, exist_ok=True)
    for root_name in ROOTS_24:
        payload = {
            "task_id": f"TASKSPEC_{root_name.upper()}_CHART_HARDENING",
            "root_id": root_name,
            "action": "full_shard_contract_and_conformance_expansion",
            "status": "queued",
            "priority": {
                "must": SHARDS_16[:4],
                "should": SHARDS_16[4:10],
                "may": SHARDS_16[10:],
            },
            "shard_ids": SHARDS_16,
            "dependencies": ["contracts", "fixtures", "registry", "reports"],
            "blockers": [],
            "required_interfaces": [f"{root_name}/shards/{shard}/interfaces/interface.yaml" for shard in SHARDS_16],
            "compliance_notes": ["ROOT-24-LOCK", "SAFE-FIX"],
            "definition_of_done": [
                "all shard contracts present",
                "all shard fixtures present",
                "registry maturity updated",
            ],
        }
        if write_yaml(registry_dir / f"TASKSPEC_{root_name}.yaml", payload):
            summary["taskspecs_created"] += 1


def append_agent_run_log(repo_root: Path, summary: dict[str, int]) -> None:
    log_path = repo_root / AGENT_RUN_RELATIVE_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "generated_at_utc": utc_now(),
        "event": "chart_manifest_bootstrap",
        "tool": "12_tooling/cli/chart_manifest_bootstrap.py",
        "summary": summary,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_bootstrap(repo_root: Path) -> dict[str, Any]:
    summary = {
        "roots_created": 0,
        "directories_created": 0,
        "module_files_created": 0,
        "readmes_created": 0,
        "shards_created": 0,
        "charts_created": 0,
        "manifests_created": 0,
        "templates_created": 0,
        "contracts_created": 0,
        "fixtures_created": 0,
        "indexes_created": 0,
        "taskspecs_created": 0,
    }
    for root_name in ROOTS_24:
        root_dir = ensure_root_scaffold(repo_root, root_name, summary)
        for shard_name in SHARDS_16:
            ensure_shard_assets(root_dir, root_name, shard_name, summary)
    ensure_taskspecs(repo_root, summary)
    registry = build_registry_snapshot(repo_root)
    write_json(repo_root / REGISTRY_RELATIVE_PATH, registry)
    append_agent_run_log(repo_root, summary)
    report = {
        "generated_at_utc": utc_now(),
        "summary": summary,
        "chart_count": len(ROOTS_24) * len(SHARDS_16),
        "manifest_count": len(ROOTS_24) * len(SHARDS_16),
        "taskspec_count": len(ROOTS_24),
        "pilot_contract_shards": [
            "03_core/01_identitaet_personen",
            "03_core/02_dokumente_nachweise",
        ],
        "registry_path": REGISTRY_RELATIVE_PATH.as_posix(),
        "agent_run_log_path": AGENT_RUN_RELATIVE_PATH.as_posix(),
    }
    write_json(repo_root / REPORT_RELATIVE_PATH, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap missing roots, shards, charts, manifests, TaskSpecs, and audit log."
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    report = run_bootstrap(args.repo_root.resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
