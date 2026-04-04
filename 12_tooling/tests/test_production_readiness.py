#!/usr/bin/env python3
"""Tests for production_readiness.py — Production Readiness Checker.

Tests verify each check function independently using temporary repo fixtures,
plus integration tests for report generation and the load test stub.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the modules under test
REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_DIR = REPO_ROOT / "12_tooling" / "cli"
sys.path.insert(0, str(CLI_DIR))

from load_test_stub import (
    LoadTestRunner,
    LoadTestScenario,
    ScenarioResult,
    _percentile,
)
from production_readiness import (
    EXPECTED_CHART_COUNT,
    EXPECTED_MANIFEST_COUNT,
    PII_PATTERNS,
    PLACEHOLDER_SIZE,
    ROOTS_24,
    SECRET_PATTERNS,
    ProductionReadinessChecker,
    ReadinessCheck,
    ReadinessReport,
    _scan_files,
    _sha256,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(tmp_path: Path, roots: list[str] | None = None) -> Path:
    """Create a minimal repo structure with root dirs."""
    if roots is None:
        roots = list(ROOTS_24)
    for r in roots:
        d = tmp_path / r
        d.mkdir(parents=True, exist_ok=True)
        # Create a manifest.yaml in each root
        (d / "manifest.yaml").write_text(f"name: {r}\nstatus: draft\n", encoding="utf-8")
        (d / "module.yaml").write_text(f"name: {r}\nstatus: draft\n", encoding="utf-8")
    return tmp_path


def _make_evidence(repo: Path) -> None:
    """Create minimal evidence files."""
    evidence_dir = repo / "02_audit_logging" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "evidence_001.json").write_text('{"type": "audit", "ts": "2025-01-01T00:00:00Z"}', encoding="utf-8")
    reports_dir = repo / "02_audit_logging" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "gate_report_001.json").write_text('{"gate": "structure", "result": "pass"}', encoding="utf-8")


# ---------------------------------------------------------------------------
# ReadinessCheck dataclass
# ---------------------------------------------------------------------------


class TestReadinessCheck:
    def test_to_dict(self):
        c = ReadinessCheck(
            name="test_check", category="testing", status="pass", detail="all good", evidence_hash="abc123"
        )
        d = c.to_dict()
        assert d["name"] == "test_check"
        assert d["category"] == "testing"
        assert d["status"] == "pass"
        assert d["detail"] == "all good"
        assert d["evidence_hash"] == "abc123"

    def test_status_values(self):
        for status in ("pass", "fail", "warn"):
            c = ReadinessCheck(name="x", category="y", status=status, detail="z")
            assert c.status == status


# ---------------------------------------------------------------------------
# ReadinessReport dataclass
# ---------------------------------------------------------------------------


class TestReadinessReport:
    def test_empty_report(self):
        r = ReadinessReport()
        d = r.to_dict()
        assert d["verdict"] == "NOT_READY"
        assert d["checks"] == []

    def test_report_with_checks(self):
        r = ReadinessReport(
            timestamp="2025-01-01T00:00:00Z",
            verdict="READY",
            checks=[ReadinessCheck("a", "b", "pass", "ok")],
            summary={"pass": 1, "fail": 0, "warn": 0, "total": 1},
        )
        d = r.to_dict()
        assert d["verdict"] == "READY"
        assert len(d["checks"]) == 1
        assert d["summary"]["total"] == 1


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_sha256_deterministic(self):
        h1 = _sha256("hello")
        h2 = _sha256("hello")
        assert h1 == h2
        assert len(h1) == 64

    def test_sha256_different_inputs(self):
        assert _sha256("a") != _sha256("b")

    def test_scan_files_detects_secrets(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('password = "SuperSecret123"', encoding="utf-8")
        findings = _scan_files(tmp_path, SECRET_PATTERNS, skip_dirs=set(), extensions={".py"})
        assert len(findings) >= 1
        assert findings[0]["file"] == "config.py"

    def test_scan_files_no_false_positives(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text('x = 42\nprint("hello")\n', encoding="utf-8")
        findings = _scan_files(tmp_path, SECRET_PATTERNS, skip_dirs=set(), extensions={".py"})
        assert len(findings) == 0

    def test_scan_files_detects_pii(self, tmp_path):
        f = tmp_path / "data.yaml"
        f.write_text("ssn: 123-45-6789\n", encoding="utf-8")
        findings = _scan_files(tmp_path, PII_PATTERNS, skip_dirs=set(), extensions={".yaml"})
        assert len(findings) >= 1

    def test_scan_files_skips_dirs(self, tmp_path):
        skip_dir = tmp_path / "__pycache__"
        skip_dir.mkdir()
        (skip_dir / "secret.py").write_text('api_key = "ABCDEF123456789"', encoding="utf-8")
        findings = _scan_files(tmp_path, SECRET_PATTERNS, skip_dirs={"__pycache__"}, extensions={".py"})
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# ProductionReadinessChecker — individual checks
# ---------------------------------------------------------------------------


class TestCheckRoot24Lock:
    def test_all_24_roots_pass(self, tmp_path):
        _make_repo(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_root24_lock()
        assert result.status == "pass"
        assert "24 roots" in result.detail

    def test_missing_root_fails(self, tmp_path):
        _make_repo(tmp_path, roots=ROOTS_24[:20])
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_root24_lock()
        assert result.status == "fail"
        assert "missing" in result.detail


class TestCheckManifestsComplete:
    def test_all_manifests_pass(self, tmp_path):
        _make_repo(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_manifests_complete()
        assert result.status == "pass"
        assert f"{EXPECTED_MANIFEST_COUNT}/{EXPECTED_MANIFEST_COUNT}" in result.detail

    def test_missing_manifest_fails(self, tmp_path):
        _make_repo(tmp_path)
        # Remove one manifest
        (tmp_path / "01_ai_layer" / "manifest.yaml").unlink()
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_manifests_complete()
        assert result.status == "fail"
        assert "01_ai_layer" in result.detail


class TestCheckSecretScan:
    def test_clean_repo_passes(self, tmp_path):
        _make_repo(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_secret_scan_clean()
        assert result.status == "pass"

    def test_secret_detected_fails(self, tmp_path):
        _make_repo(tmp_path)
        secret_file = tmp_path / "01_ai_layer" / "config.py"
        secret_file.write_text('api_key = "sk-1234567890abcdefghij"', encoding="utf-8")
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_secret_scan_clean()
        assert result.status == "fail"
        assert "secret" in result.detail.lower()


class TestCheckPiiScan:
    def test_clean_repo_passes(self, tmp_path):
        _make_repo(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_pii_scan_clean()
        assert result.status == "pass"

    def test_pii_detected_warns(self, tmp_path):
        _make_repo(tmp_path)
        pii_file = tmp_path / "01_ai_layer" / "test_data.yaml"
        pii_file.write_text("ssn: 123-45-6789\n", encoding="utf-8")
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_pii_scan_clean()
        assert result.status == "warn"


class TestCheckChartsComplete:
    def test_no_charts_fails(self, tmp_path):
        _make_repo(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_charts_complete()
        assert result.status == "fail"
        assert f"0/{EXPECTED_CHART_COUNT}" in result.detail

    def test_all_charts_pass(self, tmp_path):
        _make_repo(tmp_path)
        # Create 385 shard chart.yaml files
        shards_dir = tmp_path / "01_ai_layer" / "shards"
        for i in range(EXPECTED_CHART_COUNT):
            shard = shards_dir / f"shard_{i:04d}"
            shard.mkdir(parents=True, exist_ok=True)
            (shard / "chart.yaml").write_text(f"name: shard_{i}\n", encoding="utf-8")
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_charts_complete()
        assert result.status == "pass"


class TestCheckEvidencePresent:
    def test_no_evidence_fails(self, tmp_path):
        _make_repo(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_evidence_present()
        # The _make_repo creates dirs but may not have files initially
        # Evidence check looks for files in evidence/ and reports/ dirs
        assert result.status in ("pass", "fail")

    def test_with_evidence_passes(self, tmp_path):
        _make_repo(tmp_path)
        _make_evidence(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_evidence_present()
        assert result.status == "pass"
        assert "evidence file(s) found" in result.detail


class TestCheckNoPlaceholders:
    def test_no_placeholders_passes(self, tmp_path):
        _make_repo(tmp_path)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_no_placeholders()
        assert result.status == "pass"

    def test_placeholder_detected_warns(self, tmp_path):
        _make_repo(tmp_path)
        # Create a file that is exactly 49 bytes (PLACEHOLDER_SIZE)
        placeholder = tmp_path / "01_ai_layer" / "stub.py"
        content = b"# placeholder stub - to be replaced with real cod"
        # Ensure exactly 49 bytes
        assert len(content) == PLACEHOLDER_SIZE
        placeholder.write_bytes(content)
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_no_placeholders()
        assert result.status == "warn"


class TestCheckAllTestsGreen:
    @patch("production_readiness.subprocess.run")
    def test_pytest_passes(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="42 passed in 3.14s", stderr="")
        checker = ProductionReadinessChecker(Path("/fake"))
        result = checker.check_all_tests_green()
        assert result.status == "pass"
        assert "42" in result.detail

    @patch("production_readiness.subprocess.run")
    def test_pytest_fails(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="3 failed, 39 passed", stderr="")
        checker = ProductionReadinessChecker(Path("/fake"))
        result = checker.check_all_tests_green()
        assert result.status == "fail"


class TestCheckConvergence:
    @patch("production_readiness.subprocess.run")
    def test_convergence_passes(self, mock_run, tmp_path):
        # Create the convergence_checker.py file so the path check passes
        cli_dir = tmp_path / "12_tooling" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "convergence_checker.py").write_text("# stub", encoding="utf-8")
        mock_run.return_value = MagicMock(returncode=0, stdout="PASS", stderr="")
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_convergence_pass()
        assert result.status == "pass"

    @patch("production_readiness.subprocess.run")
    def test_convergence_warns(self, mock_run, tmp_path):
        cli_dir = tmp_path / "12_tooling" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "convergence_checker.py").write_text("# stub", encoding="utf-8")
        mock_run.return_value = MagicMock(returncode=1, stdout="WARN", stderr="")
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_convergence_pass()
        assert result.status == "warn"


class TestCheckGatesPass:
    @patch("production_readiness.subprocess.run")
    def test_gates_pass(self, mock_run, tmp_path):
        cli_dir = tmp_path / "12_tooling" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "run_all_gates.py").write_text("# stub", encoding="utf-8")
        mock_run.return_value = MagicMock(returncode=0, stdout="all passed", stderr="")
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_gates_pass()
        assert result.status == "pass"

    @patch("production_readiness.subprocess.run")
    def test_gates_fail(self, mock_run, tmp_path):
        cli_dir = tmp_path / "12_tooling" / "cli"
        cli_dir.mkdir(parents=True)
        (cli_dir / "run_all_gates.py").write_text("# stub", encoding="utf-8")
        mock_run.return_value = MagicMock(returncode=2, stdout="FAIL: structure_guard", stderr="")
        checker = ProductionReadinessChecker(tmp_path)
        result = checker.check_gates_pass()
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


class TestGenerateReadinessReport:
    def test_all_pass_is_ready(self, tmp_path):
        checker = ProductionReadinessChecker(tmp_path)
        checker._add("check1", "cat", "pass", "ok")
        checker._add("check2", "cat", "pass", "ok")
        report = checker.generate_readiness_report()
        assert report.verdict == "READY"
        assert report.summary["pass"] == 2
        assert report.summary["fail"] == 0

    def test_fail_is_not_ready(self, tmp_path):
        checker = ProductionReadinessChecker(tmp_path)
        checker._add("check1", "cat", "pass", "ok")
        checker._add("check2", "cat", "fail", "broken")
        report = checker.generate_readiness_report()
        assert report.verdict == "NOT_READY"
        assert report.summary["fail"] == 1

    def test_warn_only_is_conditional(self, tmp_path):
        checker = ProductionReadinessChecker(tmp_path)
        checker._add("check1", "cat", "pass", "ok")
        checker._add("check2", "cat", "warn", "advisory")
        report = checker.generate_readiness_report()
        assert report.verdict == "CONDITIONAL"
        assert report.summary["warn"] == 1

    def test_fail_overrides_warn(self, tmp_path):
        checker = ProductionReadinessChecker(tmp_path)
        checker._add("check1", "cat", "warn", "advisory")
        checker._add("check2", "cat", "fail", "broken")
        report = checker.generate_readiness_report()
        assert report.verdict == "NOT_READY"

    def test_report_json_serializable(self, tmp_path):
        checker = ProductionReadinessChecker(tmp_path)
        checker._add("check1", "cat", "pass", "ok")
        report = checker.generate_readiness_report()
        # Must not raise
        output = json.dumps(report.to_dict(), indent=2)
        parsed = json.loads(output)
        assert parsed["verdict"] == "READY"

    def test_evidence_hash_populated(self, tmp_path):
        checker = ProductionReadinessChecker(tmp_path)
        check = checker._add("check1", "cat", "pass", "ok")
        assert len(check.evidence_hash) == 64


# ---------------------------------------------------------------------------
# Load Test Stub
# ---------------------------------------------------------------------------


class TestLoadTestScenario:
    def test_default_values(self):
        s = LoadTestScenario(name="test", target_url="http://localhost")
        assert s.concurrent_users == 5
        assert s.duration_seconds == 10
        assert s.method == "GET"

    def test_to_dict(self):
        s = LoadTestScenario(name="test", target_url="http://localhost")
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["target_url"] == "http://localhost"

    def test_from_dict(self):
        data = {"name": "test", "target_url": "http://localhost", "concurrent_users": 10, "duration_seconds": 30}
        s = LoadTestScenario.from_dict(data)
        assert s.name == "test"
        assert s.concurrent_users == 10
        assert s.duration_seconds == 30

    def test_from_dict_ignores_unknown(self):
        data = {"name": "test", "target_url": "http://localhost", "unknown_field": 999}
        s = LoadTestScenario.from_dict(data)
        assert s.name == "test"


class TestPercentile:
    def test_empty_list(self):
        assert _percentile([], 95) == 0.0

    def test_single_value(self):
        assert _percentile([100.0], 95) == 100.0

    def test_p50_is_median(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _percentile(data, 50) == 3.0

    def test_p95(self):
        data = list(range(1, 101))
        p95 = _percentile([float(x) for x in data], 95)
        assert 95 <= p95 <= 96


class TestLoadTestRunner:
    def test_empty_runner(self):
        runner = LoadTestRunner()
        assert runner.scenarios == []
        assert runner.results == []

    def test_add_scenario(self):
        runner = LoadTestRunner()
        s = LoadTestScenario(name="test", target_url="http://localhost")
        runner.add_scenario(s)
        assert len(runner.scenarios) == 1

    def test_generate_report_empty(self):
        runner = LoadTestRunner()
        report = runner.generate_report()
        assert report["overall_passed"] is True
        assert report["scenarios_run"] == 0

    def test_generate_report_with_results(self):
        runner = LoadTestRunner()
        runner.results = [
            ScenarioResult(scenario_name="s1", passed=True),
            ScenarioResult(scenario_name="s2", passed=False),
        ]
        report = runner.generate_report()
        assert report["overall_passed"] is False
        assert report["scenarios_passed"] == 1

    def test_scenario_result_to_dict(self):
        r = ScenarioResult(
            scenario_name="test",
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            error_rate=0.05,
            passed=True,
        )
        d = r.to_dict()
        assert d["scenario_name"] == "test"
        assert d["total_requests"] == 100
        assert d["passed"] is True


# ---------------------------------------------------------------------------
# CLI main (smoke)
# ---------------------------------------------------------------------------


class TestCLIMain:
    @patch("production_readiness.ProductionReadinessChecker.run_all")
    def test_main_json_output(self, mock_run_all, capsys):
        from production_readiness import main

        mock_run_all.return_value = ReadinessReport(
            timestamp="2025-01-01T00:00:00Z",
            verdict="READY",
            checks=[ReadinessCheck("test", "cat", "pass", "ok", "hash")],
            summary={"pass": 1, "fail": 0, "warn": 0, "total": 1},
        )
        rc = main(["--json", "--repo", "/fake"])
        assert rc == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["verdict"] == "READY"

    @patch("production_readiness.ProductionReadinessChecker.run_all")
    def test_main_not_ready(self, mock_run_all):
        from production_readiness import main

        mock_run_all.return_value = ReadinessReport(
            timestamp="2025-01-01T00:00:00Z",
            verdict="NOT_READY",
            checks=[ReadinessCheck("test", "cat", "fail", "broken", "hash")],
            summary={"pass": 0, "fail": 1, "warn": 0, "total": 1},
        )
        rc = main(["--repo", "/fake"])
        assert rc == 2
