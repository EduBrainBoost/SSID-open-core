from __future__ import annotations

import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[2] / "12_tooling" / "cli"
sys.path.insert(0, str(CLI_DIR))

from chart_manifest_bootstrap import run_bootstrap
from shard_conformance_gate import _check_shard


def test_conformance_gate_passes_for_bootstrapped_shard(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    result = _check_shard("01_ai_layer", tmp_path / "01_ai_layer" / "shards" / "03_zugang_berechtigungen")
    assert result["verdict"] == "PASS"
    assert result["checks"]["manifest_contract_consistent"] is True
    assert result["checks"]["documentation_present"] is True


def test_conformance_gate_fails_closed_on_missing_contract(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    target = tmp_path / "01_ai_layer" / "shards" / "03_zugang_berechtigungen" / "contracts" / "events.schema.json"
    target.unlink()
    result = _check_shard("01_ai_layer", tmp_path / "01_ai_layer" / "shards" / "03_zugang_berechtigungen")
    assert result["verdict"] == "ERROR"
    assert any("Missing required schemas" in violation for violation in result["violations"])


def test_conformance_gate_fails_on_manifest_contract_mismatch(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    manifest = tmp_path / "01_ai_layer" / "shards" / "03_zugang_berechtigungen" / "manifest.yaml"
    content = manifest.read_text(encoding="utf-8").replace("events.schema.json", "wrong.schema.json")
    manifest.write_text(content, encoding="utf-8")
    result = _check_shard("01_ai_layer", tmp_path / "01_ai_layer" / "shards" / "03_zugang_berechtigungen")
    assert result["verdict"] == "FAIL"
    assert any("manifest/contracts mismatch" in violation for violation in result["violations"])


def test_conformance_gate_verifies_runtime_capability_for_root03_priority_shard(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    result = _check_shard("03_core", tmp_path / "03_core" / "shards" / "01_identitaet_personen")
    assert result["verdict"] == "PASS"
    assert result["checks"]["runtime_capability"] is True


def test_conformance_gate_fails_closed_on_broken_runtime_descriptor(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    runtime_index = tmp_path / "03_core" / "shards" / "01_identitaet_personen" / "runtime" / "index.yaml"
    runtime_index.parent.mkdir(parents=True, exist_ok=True)
    runtime_index.write_text(
        "schema_version: 1.0.0\nmodule: missing_runtime_module\nfactory: Root03ReferenceWave\nshard_id: 01_identitaet_personen\n",
        encoding="utf-8",
    )
    result = _check_shard("03_core", tmp_path / "03_core" / "shards" / "01_identitaet_personen")
    assert result["verdict"] == "ERROR"
    assert result["checks"]["runtime_capability"] is False
    assert any("runtime capability" in violation for violation in result["violations"])


def test_conformance_gate_verifies_cross_root_runtime_capability_for_root09_priority_shard(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    result = _check_shard("09_meta_identity", tmp_path / "09_meta_identity" / "shards" / "01_identitaet_personen")
    assert result["verdict"] == "PASS"
    assert result["checks"]["runtime_capability"] is True
    assert result["checks"]["dependency_capability"] is True
    assert result["checks"]["cross_root_runtime_capability"] is True


def test_conformance_gate_fails_closed_on_missing_cross_root_dependency(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    dependency = tmp_path / "03_core" / "shards" / "01_identitaet_personen" / "runtime" / "index.yaml"
    dependency.unlink()
    result = _check_shard("09_meta_identity", tmp_path / "09_meta_identity" / "shards" / "01_identitaet_personen")
    assert result["verdict"] == "ERROR"
    assert result["checks"]["dependency_capability"] is False
    assert result["checks"]["cross_root_runtime_capability"] is False
    assert any("cross-root runtime capability" in violation for violation in result["violations"])


def test_conformance_gate_verifies_security_enforcement_for_root07_priority_shard(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    result = _check_shard("07_governance_legal", tmp_path / "07_governance_legal" / "shards" / "01_identitaet_personen")
    assert result["verdict"] == "PASS"
    assert result["checks"]["security_capability"] is True
    assert result["checks"]["security_enforcement_capability"] is True


def test_conformance_gate_fails_closed_on_missing_security_dependency(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    dependency = tmp_path / "09_meta_identity" / "shards" / "01_identitaet_personen" / "runtime" / "index.yaml"
    dependency.unlink()
    result = _check_shard("07_governance_legal", tmp_path / "07_governance_legal" / "shards" / "01_identitaet_personen")
    assert result["verdict"] == "ERROR"
    assert result["checks"]["security_enforcement_capability"] is False
    assert any("security enforcement capability" in violation for violation in result["violations"])
