#!/usr/bin/env python3
"""Shared shard scanning, parsing, and validation primitives."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOTS_24: list[str] = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]

SHARDS_16: list[str] = [
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

MANIFEST_REQUIRED_FIELDS: list[str] = [
    "shard_id",
    "root_id",
    "version",
    "implementation_stack",
    "contracts",
    "conformance",
    "policies",
]

PII_DENY_KEYS: list[str] = [
    "name",
    "birth",
    "address",
    "doc_number",
    "email",
    "url",
]


def find_roots(repo_root: Path) -> list[Path]:
    """Return all 24 canonical root directories (sorted)."""
    return sorted(
        repo_root / name
        for name in ROOTS_24
        if (repo_root / name).is_dir()
    )


def find_shards(root_path: Path) -> list[Path]:
    """Return shard directories under <root>/shards/ (sorted)."""
    shards_dir = root_path / "shards"
    if not shards_dir.is_dir():
        return []
    return sorted(d for d in shards_dir.iterdir() if d.is_dir())


def parse_yaml(path: Path) -> dict[str, Any] | None:
    """Safe YAML parse. Returns None on any error."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_json_schema(path: Path) -> dict[str, Any] | None:
    """Safe JSON parse with basic Draft-2020-12 structure check."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def validate_manifest_fields(data: dict[str, Any]) -> list[str]:
    """Check that all required manifest fields are present. Returns list of missing field names."""
    return [f for f in MANIFEST_REQUIRED_FIELDS if f not in data]


def check_pii_keys(schema: dict[str, Any]) -> list[str]:
    """Check schema property keys against PII deny list. Returns violating key names."""
    props = schema.get("properties", {})
    return [k for k in props if k.lower() in PII_DENY_KEYS]


def write_yaml(path: Path, data: dict[str, Any]) -> bool:
    """Write YAML file (UTF-8, LF). Returns False if file exists (no-overwrite)."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    # Ensure LF line endings
    content = content.replace("\r\n", "\n")
    path.write_bytes(content.encode("utf-8"))
    return True
