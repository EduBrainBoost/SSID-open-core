#!/usr/bin/env python3
"""Tests for convergence_checker.py — Contract/Schema/Registry Convergence Audit.

Tests verify each check function independently using temporary repo fixtures,
then run an integration test against the actual SSID repo.
"""

from __future__ import annotations

import json

# Import the module under test
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_DIR = REPO_ROOT / "12_tooling" / "cli"
sys.path.insert(0, str(CLI_DIR))

from convergence_checker import (
    ConvergenceResult,
    Finding,
    check_chart_manifest_alignment,
    check_classification_convergence,
    check_contract_refs,
    check_governance_rules_convergence,
    check_registry_convergence,
    check_shard_declarations,
    check_status_version_convergence,
    check_yaml_wellformedness,
    generate_report,
    run_convergence,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_root(tmp_path: Path, root_name: str) -> Path:
    """Create a minimal root directory with module.yaml and manifest.yaml."""
    root_dir = tmp_path / root_name
    root_dir.mkdir(parents=True, exist_ok=True)
    return root_dir


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Test Finding and ConvergenceResult
# ---------------------------------------------------------------------------


class TestFinding:
    def test_to_dict(self):
        f = Finding("CVG-001", "deny", "01_ai_layer", "path/file", "detail text")
        d = f.to_dict()
        assert d["check_id"] == "CVG-001"
        assert d["severity"] == "deny"
        assert d["root"] == "01_ai_layer"
        assert d["path"] == "path/file"
        assert d["detail"] == "detail text"


class TestConvergenceResult:
    def test_empty_result_is_pass(self):
        r = ConvergenceResult()
        assert r.overall == "PASS"
        assert r.exit_code == 0

    def test_warn_result(self):
        r = ConvergenceResult()
        r.add(Finding("X", "warn", "root", "p", "d"))
        assert r.overall == "WARN"
        assert r.exit_code == 1

    def test_deny_result(self):
        r = ConvergenceResult()
        r.add(Finding("X", "deny", "root", "p", "d"))
        assert r.overall == "FAIL"
        assert r.exit_code == 2

    def test_deny_overrides_warn(self):
        r = ConvergenceResult()
        r.add(Finding("X", "warn", "root", "p", "d"))
        r.add(Finding("Y", "deny", "root", "p", "d"))
        assert r.overall == "FAIL"

    def test_evidence_hash_deterministic(self):
        r1 = ConvergenceResult()
        r1.add(Finding("A", "info", "root", "p", "d"))
        r2 = ConvergenceResult()
        r2.add(Finding("A", "info", "root", "p", "d"))
        assert r1.evidence_hash() == r2.evidence_hash()

    def test_compute_root_results(self):
        r = ConvergenceResult()
        r.add(Finding("X", "deny", "01_ai_layer", "p", "d"))
        r.add(Finding("Y", "warn", "02_audit_logging", "p", "d"))
        r.compute_root_results()
        assert r.root_results["01_ai_layer"] == "FAIL"
        assert r.root_results["02_audit_logging"] == "WARN"
        assert r.root_results["03_core"] == "PASS"


# ---------------------------------------------------------------------------
# Test CVG-001: status/version convergence
# ---------------------------------------------------------------------------


class TestCheckStatusVersion:
    def test_matching_status_version(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "module_id": "01_ai_layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
                "classification": "Public Specification",
            },
        )
        _write_yaml(
            root / "manifest.yaml",
            {
                "root_id": "01_ai_layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
            },
        )
        r = ConvergenceResult()
        check_status_version_convergence(tmp_path, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 0

    def test_mismatched_status(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "module_id": "01_ai_layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
                "classification": "X",
            },
        )
        _write_yaml(
            root / "manifest.yaml",
            {
                "root_id": "01_ai_layer",
                "status": "draft",
                "version": "4.1.0",
            },
        )
        r = ConvergenceResult()
        check_status_version_convergence(tmp_path, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 1
        assert "status mismatch" in denies[0].detail

    def test_mismatched_version(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "module_id": "01_ai_layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
                "classification": "X",
            },
        )
        _write_yaml(
            root / "manifest.yaml",
            {
                "root_id": "01_ai_layer",
                "status": "ROOT-24-LOCK",
                "version": "1.0.0",
            },
        )
        r = ConvergenceResult()
        check_status_version_convergence(tmp_path, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 1
        assert "version mismatch" in denies[0].detail


# ---------------------------------------------------------------------------
# Test CVG-002: classification convergence
# ---------------------------------------------------------------------------


class TestCheckClassification:
    def test_matching_classification(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(root / "module.yaml", {"classification": "Public Specification"})
        _write_yaml(root / "manifest.yaml", {"classification": "Public Specification"})
        r = ConvergenceResult()
        check_classification_convergence(tmp_path, r)
        assert len(r.findings) == 0

    def test_mismatched_classification(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(root / "module.yaml", {"classification": "Data Management"})
        _write_yaml(root / "manifest.yaml", {"classification": "Data Infrastructure"})
        r = ConvergenceResult()
        check_classification_convergence(tmp_path, r)
        warns = [f for f in r.findings if f.severity == "warn"]
        assert len(warns) == 1


# ---------------------------------------------------------------------------
# Test CVG-003: contract refs
# ---------------------------------------------------------------------------


class TestCheckContractRefs:
    def test_existing_contract_ref(self, tmp_path):
        root = _make_root(tmp_path, "03_core")
        contracts_dir = root / "contracts" / "dispatcher"
        contracts_dir.mkdir(parents=True)
        _write_yaml(
            root / "manifest.yaml",
            {
                "contracts": [{"ref": "contracts/dispatcher/"}],
            },
        )
        r = ConvergenceResult()
        check_contract_refs(tmp_path, r)
        assert len([f for f in r.findings if f.severity == "deny"]) == 0

    def test_missing_contract_ref(self, tmp_path):
        root = _make_root(tmp_path, "03_core")
        _write_yaml(
            root / "manifest.yaml",
            {
                "contracts": [{"ref": "contracts/missing/"}],
            },
        )
        r = ConvergenceResult()
        check_contract_refs(tmp_path, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 1
        assert "does not exist" in denies[0].detail


# ---------------------------------------------------------------------------
# Test CVG-004: shard declarations
# ---------------------------------------------------------------------------


class TestCheckShardDeclarations:
    def test_matching_shards(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        shards = root / "shards"
        (shards / "shard_a").mkdir(parents=True)
        (shards / "shard_b").mkdir(parents=True)
        _write_yaml(
            root / "manifest.yaml",
            {
                "shards": {
                    "count": 2,
                    "shards_list": ["shard_a", "shard_b"],
                },
            },
        )
        r = ConvergenceResult()
        check_shard_declarations(tmp_path, r)
        assert len(r.findings) == 0

    def test_extra_shard_on_disk(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        shards = root / "shards"
        (shards / "shard_a").mkdir(parents=True)
        (shards / "shard_b").mkdir(parents=True)
        (shards / "shard_c").mkdir(parents=True)
        _write_yaml(
            root / "manifest.yaml",
            {
                "shards": {
                    "count": 2,
                    "shards_list": ["shard_a", "shard_b"],
                },
            },
        )
        r = ConvergenceResult()
        check_shard_declarations(tmp_path, r)
        warns = [f for f in r.findings if f.severity == "warn"]
        assert len(warns) >= 1

    def test_missing_shard_on_disk(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        shards = root / "shards"
        (shards / "shard_a").mkdir(parents=True)
        _write_yaml(
            root / "manifest.yaml",
            {
                "shards": {
                    "count": 2,
                    "shards_list": ["shard_a", "shard_b"],
                },
            },
        )
        r = ConvergenceResult()
        check_shard_declarations(tmp_path, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 1
        assert "shard_b" in denies[0].detail


# ---------------------------------------------------------------------------
# Test CVG-005: chart/manifest alignment
# ---------------------------------------------------------------------------


class TestCheckChartManifestAlignment:
    def test_matching_root_and_shard(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        shard = root / "shards" / "01_identitaet_personen"
        shard.mkdir(parents=True)
        _write_yaml(
            shard / "chart.yaml",
            {
                "root": "01_ai_layer",
                "shard": "01_identitaet_personen",
                "status": "draft",
            },
        )
        _write_yaml(
            shard / "manifest.yaml",
            {
                "root_id": "01_ai_layer",
                "shard_id": "01_identitaet_personen",
            },
        )
        r = ConvergenceResult()
        check_chart_manifest_alignment(tmp_path, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 0

    def test_mismatched_shard_id(self, tmp_path):
        root = _make_root(tmp_path, "03_core")
        shard = root / "shards" / "01_identitaet_personen"
        shard.mkdir(parents=True)
        _write_yaml(
            shard / "chart.yaml",
            {
                "root": "03_core",
                "shard": "01_identitaet_personen",
            },
        )
        _write_yaml(
            shard / "manifest.yaml",
            {
                "root_id": "03_core",
                "shard_id": "03_core/01_identitaet_personen",
            },
        )
        r = ConvergenceResult()
        check_chart_manifest_alignment(tmp_path, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 1
        assert "shard id mismatch" in denies[0].detail


# ---------------------------------------------------------------------------
# Test CVG-006: registry convergence
# ---------------------------------------------------------------------------


class TestCheckRegistryConvergence:
    def test_matching_registry(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "module_id": "01_ai_layer",
                "name": "AI Layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
                "classification": "X",
            },
        )
        registry_modules = {
            "01_ai_layer": {
                "module_id": "01_ai_layer",
                "name": "AI Layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
            },
        }
        r = ConvergenceResult()
        check_registry_convergence(tmp_path, registry_modules, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 0

    def test_missing_in_registry(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "module_id": "01_ai_layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
                "classification": "X",
            },
        )
        r = ConvergenceResult()
        check_registry_convergence(tmp_path, {}, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 1
        assert "no entry in registry" in denies[0].detail

    def test_status_mismatch_registry(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "module_id": "01_ai_layer",
                "status": "ROOT-24-LOCK",
                "version": "4.1.0",
                "classification": "X",
            },
        )
        registry_modules = {
            "01_ai_layer": {
                "module_id": "01_ai_layer",
                "status": "active",
                "version": "4.1.0",
            },
        }
        r = ConvergenceResult()
        check_registry_convergence(tmp_path, registry_modules, r)
        denies = [f for f in r.findings if f.severity == "deny"]
        assert len(denies) == 1


# ---------------------------------------------------------------------------
# Test CVG-008: YAML well-formedness
# ---------------------------------------------------------------------------


class TestCheckYamlWellformedness:
    def test_valid_yaml(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(root / "module.yaml", {"module_id": "01_ai_layer"})
        _write_yaml(root / "manifest.yaml", {"root_id": "01_ai_layer"})
        r = ConvergenceResult()
        check_yaml_wellformedness(tmp_path, r)
        # Filter findings for just 01_ai_layer (other roots don't exist in tmp_path)
        root_findings = [f for f in r.findings if f.root == "01_ai_layer"]
        assert len(root_findings) == 0

    def test_bom_detection(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        # Write module.yaml with BOM
        bom_content = b"\xef\xbb\xbf" + b'module_id: "01_ai_layer"\n'
        (root / "module.yaml").write_bytes(bom_content)
        _write_yaml(root / "manifest.yaml", {"root_id": "01_ai_layer"})
        r = ConvergenceResult()
        check_yaml_wellformedness(tmp_path, r)
        warns = [f for f in r.findings if f.severity == "warn" and "BOM" in f.detail]
        assert len(warns) == 1

    def test_missing_module_yaml(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(root / "manifest.yaml", {"root_id": "01_ai_layer"})
        r = ConvergenceResult()
        check_yaml_wellformedness(tmp_path, r)
        # Filter for just 01_ai_layer
        denies = [f for f in r.findings if f.severity == "deny" and f.root == "01_ai_layer"]
        assert len(denies) == 1
        assert "does not exist" in denies[0].detail


# ---------------------------------------------------------------------------
# Test CVG-009: governance rules convergence
# ---------------------------------------------------------------------------


class TestCheckGovernanceRules:
    def test_matching_rules(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "governance_rules": ["SOT_AGENT_006", "SOT_AGENT_007"],
            },
        )
        _write_yaml(
            root / "manifest.yaml",
            {
                "governance_rules": ["SOT_AGENT_006", "SOT_AGENT_007"],
            },
        )
        r = ConvergenceResult()
        check_governance_rules_convergence(tmp_path, r)
        assert len(r.findings) == 0

    def test_module_has_rules_manifest_empty(self, tmp_path):
        root = _make_root(tmp_path, "01_ai_layer")
        _write_yaml(
            root / "module.yaml",
            {
                "governance_rules": ["SOT_AGENT_006"],
            },
        )
        _write_yaml(
            root / "manifest.yaml",
            {
                "governance_rules": [],
            },
        )
        r = ConvergenceResult()
        check_governance_rules_convergence(tmp_path, r)
        infos = [f for f in r.findings if f.severity == "info"]
        assert len(infos) == 1


# ---------------------------------------------------------------------------
# Test generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_report_structure(self, tmp_path):
        r = ConvergenceResult()
        r.add(Finding("CVG-001", "deny", "01_ai_layer", "p", "detail"))
        r.add(Finding("CVG-002", "warn", "02_audit_logging", "p", "detail"))
        r.add(Finding("CVG-005", "info", "03_core", "p", "detail"))
        r.compute_root_results()
        report = generate_report(r, tmp_path)
        assert report["audit_type"] == "convergence_check"
        assert report["overall"] == "FAIL"
        assert report["deny_count"] == 1
        assert report["warn_count"] == 1
        assert report["info_count"] == 1
        assert report["finding_count"] == 3
        assert "evidence_hash" in report
        assert "root_results" in report
        assert "findings" in report


# ---------------------------------------------------------------------------
# Integration test: run against real SSID repo
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_convergence_on_real_repo(self):
        """Run convergence check on the actual SSID repository.

        After fixes, all roots should PASS (no deny or warn findings).
        """
        result = run_convergence(REPO_ROOT)
        report = generate_report(result, REPO_ROOT)

        # No deny findings
        assert report["deny_count"] == 0, f"Found {report['deny_count']} deny findings: " + json.dumps(
            [f for f in report["findings"] if f["severity"] == "deny"],
            indent=2,
        )

        # No warn findings
        assert report["warn_count"] == 0, f"Found {report['warn_count']} warn findings: " + json.dumps(
            [f for f in report["findings"] if f["severity"] == "warn"],
            indent=2,
        )

        # All 24 roots present
        assert len(report["root_results"]) == 24

        # All PASS
        for root, status in report["root_results"].items():
            assert status == "PASS", f"{root} has status {status}"

    def test_report_file_exists(self):
        """Verify the convergence report was generated."""
        report_path = REPO_ROOT / "02_audit_logging" / "reports" / "convergence_report.json"
        assert report_path.exists(), f"Report not found: {report_path}"

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["audit_type"] == "convergence_check"
        assert report["overall"] == "PASS"
        assert report["deny_count"] == 0
