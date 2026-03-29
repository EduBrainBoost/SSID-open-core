from __future__ import annotations

import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[2] / "12_tooling" / "cli"
sys.path.insert(0, str(CLI_DIR))

from chart_manifest_bootstrap import run_bootstrap
from shards_registry_build import build_registry
from _lib.shards import find_roots


def test_registry_marks_shards_conformance_ready(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    registry = build_registry(find_roots(tmp_path), deterministic=True)
    assert registry["shard_count"] == 384
    assert all(entry["contract_status"] == "ready" for entry in registry["shards"])
    assert all(entry["conformance_status"] == "ready" for entry in registry["shards"])
    assert all(entry["verification_result"] == "PASS" for entry in registry["shards"])


def test_registry_is_deterministic_for_same_input(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    registry_a = build_registry(find_roots(tmp_path), deterministic=True)
    registry_b = build_registry(find_roots(tmp_path), deterministic=True)
    assert registry_a["shard_count"] == registry_b["shard_count"]
    assert registry_a["shards"] == registry_b["shards"]


def test_registry_marks_root03_priority_shards_runtime_ready(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    registry = build_registry(find_roots(tmp_path), deterministic=True)
    runtime_ready = {
        (entry["root_id"], entry["shard_id"]): entry
        for entry in registry["shards"]
        if entry["root_id"] == "03_core" and entry["runtime_status"] == "ready"
    }
    assert set(runtime_ready) == {
        ("03_core", "01_identitaet_personen"),
        ("03_core", "02_dokumente_nachweise"),
        ("03_core", "03_zugang_berechtigungen"),
        ("03_core", "04_kommunikation_daten"),
        ("03_core", "05_gesundheit_medizin"),
    }
    assert all(entry["status"] == "runtime_ready" for entry in runtime_ready.values())


def test_registry_marks_root09_priority_shards_cross_root_runtime_ready(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    registry = build_registry(find_roots(tmp_path), deterministic=True)
    runtime_ready = {
        (entry["root_id"], entry["shard_id"]): entry
        for entry in registry["shards"]
        if entry["root_id"] == "09_meta_identity" and entry["dependency_status"] == "ready"
    }
    assert set(runtime_ready) == {
        ("09_meta_identity", "01_identitaet_personen"),
        ("09_meta_identity", "02_dokumente_nachweise"),
        ("09_meta_identity", "03_zugang_berechtigungen"),
        ("09_meta_identity", "04_kommunikation_daten"),
        ("09_meta_identity", "05_gesundheit_medizin"),
    }
    assert all(entry["status"] == "cross_root_runtime_ready" for entry in runtime_ready.values())
    assert all(entry["service_runtime_status"] == "ready" for entry in runtime_ready.values())
    assert all(entry["runtime_dependency_refs"] for entry in runtime_ready.values())


def test_registry_marks_root07_priority_shards_security_enforced(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    registry = build_registry(find_roots(tmp_path), deterministic=True)
    enforced = {
        (entry["root_id"], entry["shard_id"]): entry
        for entry in registry["shards"]
        if entry["root_id"] == "07_governance_legal" and entry["security_enforced"] is True
    }
    assert set(enforced) == {
        ("07_governance_legal", "01_identitaet_personen"),
        ("07_governance_legal", "02_dokumente_nachweise"),
        ("07_governance_legal", "03_zugang_berechtigungen"),
        ("07_governance_legal", "04_kommunikation_daten"),
        ("07_governance_legal", "05_gesundheit_medizin"),
    }
    assert all(entry["security_status"] == "ready" for entry in enforced.values())
