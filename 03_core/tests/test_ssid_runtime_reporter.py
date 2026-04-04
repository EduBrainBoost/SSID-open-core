"""Tests for SsidRuntimeReporter — P5.1/P5.2."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ems_contract import SCHEMA_VERSION
from ssid_runtime_reporter import SsidRuntimeReport, SsidRuntimeReporter


def test_generate_report_returns_runtime_report():
    """generate_report() returns a SsidRuntimeReport instance."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    assert isinstance(report, SsidRuntimeReport)


def test_report_has_3_flow_statuses():
    """report.flow_statuses has exactly 3 entries."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    assert len(report.flow_statuses) == 3


def test_all_flows_succeed():
    """All 3 flow statuses have status == 'success'."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    for flow in report.flow_statuses:
        assert flow.get("status") == "success", (
            f"Flow {flow.get('flow_name')} has status {flow.get('status')!r}, error: {flow.get('error', 'n/a')}"
        )


def test_module_health_has_8_entries():
    """report.module_health has 8 entries, all with status == 'healthy'."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    assert len(report.module_health) == 8
    for entry in report.module_health:
        assert entry["status"] == "healthy", f"Module {entry['module_name']} is not healthy: {entry['status']!r}"


def test_schema_version_matches():
    """report.schema_version matches the imported SCHEMA_VERSION."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    assert report.schema_version == SCHEMA_VERSION


def test_to_json_is_valid_json():
    """report.to_json() produces a string that parses back to a dict without error."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    raw = report.to_json()
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
    assert "flow_statuses" in parsed
    assert "module_health" in parsed


def test_export_to_file_writes_json(tmp_path):
    """export_to_file() writes a valid JSON file to the given path."""
    reporter = SsidRuntimeReporter()
    out_path = tmp_path / "status.json"
    returned_path = reporter.export_to_file(out_path)
    assert returned_path == out_path
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert isinstance(parsed, dict)
    assert len(parsed["flow_statuses"]) == 3


def test_flow_statuses_have_proof_hash():
    """All 3 flow statuses have a proof_hash that is a 64-char hex string."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    hex_pattern = re.compile(r"^[0-9a-f]{64}$")
    for flow in report.flow_statuses:
        proof_hash = flow.get("proof_hash")
        assert proof_hash is not None, f"Flow {flow.get('flow_name')} has no proof_hash"
        assert hex_pattern.match(proof_hash), (
            f"Flow {flow.get('flow_name')} proof_hash {proof_hash!r} is not 64-char hex"
        )
