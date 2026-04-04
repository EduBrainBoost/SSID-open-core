"""Tests for negative runtime report states — P5-PreMerge P2."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ssid_runtime_reporter import SsidRuntimeReporter


@pytest.fixture
def reporter() -> SsidRuntimeReporter:
    return SsidRuntimeReporter()


def test_denied_report_has_denied_flow(reporter):
    """generate_denied_report() → at least one flow with status == 'denied'."""
    report = reporter.generate_denied_report()
    statuses = [f["status"] for f in report.flow_statuses]
    assert "denied" in statuses


def test_denied_report_flow_allow_or_deny_is_deny(reporter):
    """Denied flow has allow_or_deny == 'deny'."""
    report = reporter.generate_denied_report()
    denied_flows = [f for f in report.flow_statuses if f.get("status") == "denied"]
    assert denied_flows, "Expected at least one denied flow"
    for flow in denied_flows:
        assert flow.get("allow_or_deny") == "deny"


def test_denied_report_proof_hash_is_none(reporter):
    """Denied flow proof_hash is None."""
    report = reporter.generate_denied_report()
    denied_flows = [f for f in report.flow_statuses if f.get("status") == "denied"]
    assert denied_flows, "Expected at least one denied flow"
    for flow in denied_flows:
        assert flow.get("proof_hash") is None


def test_denied_report_has_policy_decisions(reporter):
    """Denied flow policy_decisions is non-empty list."""
    report = reporter.generate_denied_report()
    denied_flows = [f for f in report.flow_statuses if f.get("status") == "denied"]
    assert denied_flows, "Expected at least one denied flow"
    for flow in denied_flows:
        decisions = flow.get("policy_decisions")
        assert isinstance(decisions, list)
        assert len(decisions) > 0


def test_denied_report_modules_still_healthy(reporter):
    """Even when flow denied, module_health all status == 'healthy'."""
    report = reporter.generate_denied_report()
    for module in report.module_health:
        assert module["status"] == "healthy", f"Module {module['module_name']} expected healthy, got {module['status']}"


def test_degraded_report_has_degraded_module(reporter):
    """generate_degraded_report('fee_proof_engine') → one module has status == 'degraded'."""
    report = reporter.generate_degraded_report("fee_proof_engine")
    degraded = [m for m in report.module_health if m["status"] == "degraded"]
    assert len(degraded) == 1
    assert degraded[0]["module_name"] == "fee_proof_engine"


def test_degraded_report_other_modules_healthy(reporter):
    """All other 7 modules still healthy when one is degraded."""
    report = reporter.generate_degraded_report("fee_proof_engine")
    healthy = [m for m in report.module_health if m["status"] == "healthy"]
    assert len(healthy) == 7


def test_degraded_report_flows_still_succeed(reporter):
    """Flows in degraded report have status == 'success' (module degraded flag doesn't block flows)."""
    report = reporter.generate_degraded_report("fee_proof_engine")
    for flow in report.flow_statuses:
        assert flow.get("status") == "success", (
            f"Flow {flow.get('flow_name')} expected success, got {flow.get('status')}: {flow.get('error', '')}"
        )


def test_denied_report_is_valid_json(reporter):
    """generate_denied_report().to_json() → valid JSON string."""
    report = reporter.generate_denied_report()
    json_str = report.to_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)


def test_degraded_report_is_valid_json(reporter):
    """generate_degraded_report().to_json() → valid JSON string."""
    report = reporter.generate_degraded_report()
    json_str = report.to_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)
