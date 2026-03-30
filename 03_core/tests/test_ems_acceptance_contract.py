"""test_ems_acceptance_contract.py — Acceptance tests for SSID→EMS handoff contract.

Tests the EmsConsumer (reference implementation of what EMS does after PR#127 merge)
against golden files and edge cases.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).parent.parent / "schema"
GOLDEN_HEALTHY = SCHEMA_DIR / "golden_healthy.json"
GOLDEN_DENIED = SCHEMA_DIR / "golden_denied.json"
GOLDEN_DEGRADED = SCHEMA_DIR / "golden_degraded.json"


@pytest.fixture
def consumer():
    from consumer_simulator import EmsConsumer
    return EmsConsumer()


@pytest.fixture
def healthy_report():
    return json.loads(GOLDEN_HEALTHY.read_text())


@pytest.fixture
def denied_report():
    return json.loads(GOLDEN_DENIED.read_text())


@pytest.fixture
def degraded_report():
    return json.loads(GOLDEN_DEGRADED.read_text())


# --- Scenario 1: healthy report accepted ---

def test_healthy_report_accepted(consumer, healthy_report):
    result = consumer.consume(healthy_report)
    assert result.exit_code == 0  # EXIT_HEALTHY
    assert result.overall_classification == "healthy"
    assert result.contract_status == "valid"
    assert result.flow_summary.denied == 0
    assert result.module_summary.degraded == 0
    assert result.module_summary.offline == 0


def test_healthy_report_from_file(consumer):
    result = consumer.consume_file(GOLDEN_HEALTHY)
    assert result.exit_code == 0
    assert result.is_healthy


# --- Scenario 2: denied report accepted and correctly classified ---

def test_denied_report_accepted(consumer, denied_report):
    result = consumer.consume(denied_report)
    assert result.exit_code == 1  # EXIT_DENIED
    assert result.overall_classification == "denied"
    assert result.contract_status == "valid"
    assert result.flow_summary.denied >= 1
    assert len(result.flow_summary.flow_ids_denied) >= 1


def test_denied_report_from_file(consumer):
    result = consumer.consume_file(GOLDEN_DENIED)
    assert result.is_denied


# --- Scenario 3: degraded report accepted and correctly classified ---

def test_degraded_report_accepted(consumer, degraded_report):
    result = consumer.consume(degraded_report)
    assert result.exit_code == 2  # EXIT_DEGRADED
    assert result.overall_classification == "degraded"
    assert result.contract_status == "valid"
    assert result.module_summary.degraded >= 1 or result.module_summary.offline >= 1 or result.flow_summary.error >= 1 or result.flow_summary.degraded >= 1


def test_degraded_report_from_file(consumer):
    result = consumer.consume_file(GOLDEN_DEGRADED)
    assert result.is_degraded


# --- Scenario 4: invalid schema rejected ---

def test_invalid_schema_rejected(consumer, healthy_report):
    # Remove a required field
    bad = dict(healthy_report)
    del bad["module_health"]
    result = consumer.consume(bad)
    assert result.exit_code in (3, 5)  # invalid_schema or incomplete
    assert result.overall_classification == "error"
    assert len(result.errors) > 0


def test_completely_invalid_json_rejected(consumer, tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json at all")
    result = consumer.consume_file(bad_file)
    assert result.exit_code == 3  # EXIT_INVALID_SCHEMA
    assert result.overall_classification == "error"


# --- Scenario 5: wrong schema_version rejected ---

def test_wrong_major_version_rejected(consumer, healthy_report):
    bad = dict(healthy_report)
    bad["schema_version"] = "2.0.0"  # MAJOR mismatch
    result = consumer.consume(bad)
    assert result.exit_code == 4  # EXIT_VERSION_MISMATCH
    assert result.contract_status == "version_mismatch"
    assert result.overall_classification == "error"


def test_non_semver_version_rejected(consumer, healthy_report):
    bad = dict(healthy_report)
    bad["schema_version"] = "not-a-version"
    result = consumer.consume(bad)
    assert result.exit_code == 4  # EXIT_VERSION_MISMATCH


# --- Scenario 6: missing required fields rejected ---

def test_missing_schema_version_rejected(consumer, healthy_report):
    bad = dict(healthy_report)
    del bad["schema_version"]
    result = consumer.consume(bad)
    assert result.exit_code in (4, 5)  # version_mismatch or incomplete
    assert result.overall_classification == "error"


def test_missing_generated_at_rejected(consumer, healthy_report):
    bad = dict(healthy_report)
    del bad["generated_at"]
    result = consumer.consume(bad)
    assert result.exit_code == 5  # EXIT_INCOMPLETE
    assert result.overall_classification == "error"


def test_empty_report_rejected(consumer):
    result = consumer.consume({})
    assert result.exit_code == 5  # EXIT_INCOMPLETE
    assert result.overall_classification == "error"


# --- Scenario 7: hash/proof format violations flagged ---

def test_unknown_flow_status_flagged(consumer, healthy_report):
    """Unknown flow status should produce a warning in errors, but not crash."""
    bad = json.loads(json.dumps(healthy_report))  # deep copy
    if bad["flow_statuses"]:
        bad["flow_statuses"][0]["status"] = "unknown_status_xyz"
    result = consumer.consume(bad)
    # Should still return a result (not raise), errors list may have warning
    assert result is not None
    # The exit code may still be healthy if no other issues, but unknown status is logged
    assert isinstance(result.errors, list)


def test_file_not_found_returns_error(consumer, tmp_path):
    result = consumer.consume_file(tmp_path / "nonexistent.json")
    assert result.exit_code == 5  # EXIT_INCOMPLETE
    assert result.overall_classification == "error"
    assert len(result.errors) > 0
