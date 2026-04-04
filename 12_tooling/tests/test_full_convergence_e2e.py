#!/usr/bin/env python3
"""E2E tests for full SoT convergence pipeline (PR-6 FULL_CONVERGENCE_E2E_HARDENING).

Tests cover: canonical pass, derivative leakage denial, contract hash mismatch,
missing artifacts, deterministic aggregation, EMS publish payload validity,
and repeated-run idempotency.

All external dependencies (scanner, manifest gen, opencore sync, git, filesystem)
are mocked. No scores -- PASS/FAIL + findings only.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import pipeline internals under test
# ---------------------------------------------------------------------------
from cli.run_sot_convergence import (
    EXIT_DENY,
    EXIT_SUCCESS,
    _collect,
    _decide,
    _json_report,
    _run_identity,
    _step_policy,
)

# Alias the user-requested name so intent is clear in test names.
_step_policy_check = _step_policy

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "validation" / "sot_finding_schema.json"

# ---------------------------------------------------------------------------
# Fixtures -- canonical scan / sync results
# ---------------------------------------------------------------------------


def _clean_scan(
    status: str = "PASS", drift: list[dict[str, Any]] | None = None, missing: list[str] | None = None
) -> dict[str, Any]:
    """Build a minimal scanner result dict."""
    return {
        "status": status,
        "repo_role": "canonical",
        "drift_findings": drift or [],
        "missing_artifacts": missing or [],
        "root_count": 24,
    }


def _clean_sync(status: str = "pass", findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a minimal opencore-sync result dict."""
    return {
        "status": status,
        "findings": findings or [],
        "registry_binding_status": "consistent",
    }


@pytest.fixture()
def tmp_repos(tmp_path: Path):
    """Create minimal canonical + derivative directory trees."""
    canonical = tmp_path / "ssid"
    derivative = tmp_path / "ssid-open-core"
    canonical.mkdir()
    derivative.mkdir()
    # Provide a contract file so _sha256_file / _contract_version work
    contract = canonical / "16_codex" / "contracts" / "sot"
    contract.mkdir(parents=True)
    (contract / "sot_contract.yaml").write_text("version: '4.1.0'\nrules: []\n", encoding="utf-8")
    return canonical, derivative


# ===================================================================
# 1. test_canonical_pass
# ===================================================================


@patch("cli.run_sot_convergence.opencore_scan", return_value=_clean_sync())
@patch("cli.run_sot_convergence.generate_manifest", return_value="{}")
@patch("cli.run_sot_convergence.render_report", return_value="")
@patch("cli.run_sot_convergence.scanner_scan", return_value=_clean_scan())
@patch("cli.run_sot_convergence._git_head", return_value="abc123")
def test_canonical_pass(_mock_git, _mock_scanner, _mock_render, _mock_manifest, _mock_oc, tmp_repos):
    """Successful run with clean scan + sync produces PASS / exit 0."""
    canonical, derivative = tmp_repos

    scan = _clean_scan()
    sync = _clean_sync()
    policy = _step_policy_check(scan, sync)
    findings = _collect(scan, sync, policy)
    decision, exit_code = _decide(findings)

    assert decision == "pass", f"Expected 'pass', got '{decision}'"
    assert exit_code == EXIT_SUCCESS
    assert len(findings) == 0


# ===================================================================
# 2. test_derivative_leakage_fail
# ===================================================================


def test_derivative_leakage_fail():
    """A 'forbidden_export' finding in sync must produce a DENY decision."""
    scan = _clean_scan()
    sync = _clean_sync(
        status="fail",
        findings=[
            {
                "class": "forbidden_export",
                "severity": "critical",
                "path": "03_core/secrets/key.pem",
                "detail": "Forbidden file exported to derivative",
            },
        ],
    )

    policy = _step_policy_check(scan, sync)
    findings = _collect(scan, sync, policy)
    decision, exit_code = _decide(findings)

    assert exit_code == EXIT_DENY, f"Expected EXIT_DENY(2), got {exit_code}"
    assert decision == "fail"
    deny_classes = [f["class"] for f in findings if f["class"] == "policy_deny"]
    assert len(deny_classes) >= 1, "Expected at least one policy_deny finding"


# ===================================================================
# 3. test_contract_hash_mismatch_fail
# ===================================================================


def test_contract_hash_mismatch_fail():
    """A 'contract_hash_mismatch' sync finding must trigger DENY."""
    scan = _clean_scan()
    sync = _clean_sync(
        status="fail",
        findings=[
            {
                "class": "contract_hash_mismatch",
                "severity": "critical",
                "path": "16_codex/contracts/sot/sot_contract.yaml",
                "detail": "SHA-256 mismatch between canonical and derivative contract",
            },
        ],
    )

    policy = _step_policy_check(scan, sync)
    findings = _collect(scan, sync, policy)
    decision, exit_code = _decide(findings)

    assert exit_code == EXIT_DENY
    assert decision == "fail"
    policy_denies = [f for f in findings if f["class"] == "policy_deny"]
    assert any("contract_hash_mismatch" in f["details"] for f in policy_denies), (
        "DENY finding must reference contract_hash_mismatch"
    )


# ===================================================================
# 4. test_missing_expected_artifacts
# ===================================================================


def test_missing_expected_artifacts():
    """Missing artifacts in a canonical scan produce a DENY finding."""
    scan = _clean_scan(
        status="FAIL",
        missing=["03_core/README.md", "12_tooling/module.yaml"],
    )
    sync = _clean_sync()

    policy = _step_policy_check(scan, sync)
    findings = _collect(scan, sync, policy)
    decision, exit_code = _decide(findings)

    assert exit_code == EXIT_DENY
    assert decision == "fail"
    deny_details = " ".join(f["details"] for f in findings if f["class"] == "policy_deny")
    assert "missing artifacts" in deny_details.lower() or "CONVERGENCE_DENY" in deny_details, (
        "DENY finding must reference missing artifacts"
    )


# ===================================================================
# 5. test_deterministic_aggregator_output
# ===================================================================


def test_deterministic_aggregator_output():
    """Given identical inputs, _collect + _decide must return identical output."""
    scan = _clean_scan(
        drift=[
            {
                "class": "stale_derivative_binding",
                "severity": "medium",
                "path": "03_core/bindings.json",
                "detail": "stale hash",
            },
        ]
    )
    sync = _clean_sync(
        findings=[
            {
                "class": "missing_expected_export",
                "severity": "medium",
                "path": "docs/overview.md",
                "detail": "not exported",
            },
        ]
    )

    policy_a = _step_policy_check(copy.deepcopy(scan), copy.deepcopy(sync))
    findings_a = _collect(copy.deepcopy(scan), copy.deepcopy(sync), policy_a)
    decision_a, exit_a = _decide(findings_a)

    policy_b = _step_policy_check(copy.deepcopy(scan), copy.deepcopy(sync))
    findings_b = _collect(copy.deepcopy(scan), copy.deepcopy(sync), policy_b)
    decision_b, exit_b = _decide(findings_b)

    assert decision_a == decision_b, "Decision must be deterministic"
    assert exit_a == exit_b, "Exit code must be deterministic"
    assert json.dumps(findings_a, sort_keys=True) == json.dumps(findings_b, sort_keys=True), (
        "Finding list must be byte-identical for identical inputs"
    )


# ===================================================================
# 6. test_ems_publish_payload_validity
# ===================================================================


def test_ems_publish_payload_validity(tmp_repos):
    """The audit event payload written by _json_report must contain all
    required fields matching the sot_finding_schema.json summary contract."""
    canonical, derivative = tmp_repos
    scan = _clean_scan()
    sync = _clean_sync()
    policy = _step_policy_check(scan, sync)
    findings = _collect(scan, sync, policy)
    decision, exit_code = _decide(findings)

    with patch("cli.run_sot_convergence._git_head", return_value="deadbeef"):
        rid = _run_identity(canonical, derivative, findings, decision, json.dumps(findings, sort_keys=True))

    report = _json_report(scan, "{}", sync, findings, decision, exit_code, rid)

    # -- Structural assertions against the report payload --
    assert "report_version" in report
    assert "run_identity" in report
    assert "decision" in report
    assert "exit_code" in report
    assert "findings" in report
    assert isinstance(report["findings"], list)
    assert "summary" in report
    summary = report["summary"]
    assert "total_findings" in summary
    assert "max_severity" in summary

    # Validate run_identity sub-fields
    rid_out = report["run_identity"]
    for key in ("run_id", "timestamp_utc", "contract_sha256", "contract_version", "decision", "evidence_sha256"):
        assert key in rid_out, f"run_identity missing key '{key}'"

    # Validate that the schema file itself is loadable (meta-check)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["title"] == "SoT Convergence Findings"

    # Cross-check: decision in report matches summary expectation
    assert report["decision"] == decision


# ===================================================================
# 7. test_repeated_run_idempotency
# ===================================================================


@patch("cli.run_sot_convergence._git_head", return_value="aaa111")
def test_repeated_run_idempotency(_mock_git, tmp_repos):
    """Running the pipeline twice with identical inputs must produce
    identical decisions, exit codes, and finding lists."""
    canonical, derivative = tmp_repos
    scan = _clean_scan(
        drift=[
            {
                "class": "enforcement_gap",
                "severity": "low",
                "path": "05_governance/gaps.md",
                "detail": "uncovered rule",
            },
        ]
    )
    sync = _clean_sync(
        findings=[
            {"class": "missing_expected_export", "severity": "medium", "path": "docs/api.md", "detail": "not exported"},
        ]
    )

    results = []
    for _ in range(3):
        s, sy = copy.deepcopy(scan), copy.deepcopy(sync)
        policy = _step_policy_check(s, sy)
        findings = _collect(s, sy, policy)
        decision, exit_code = _decide(findings)
        results.append(
            {
                "decision": decision,
                "exit_code": exit_code,
                "findings_json": json.dumps(findings, sort_keys=True),
            }
        )

    for i in range(1, len(results)):
        assert results[0]["decision"] == results[i]["decision"], f"Decision diverged on run {i + 1}"
        assert results[0]["exit_code"] == results[i]["exit_code"], f"Exit code diverged on run {i + 1}"
        assert results[0]["findings_json"] == results[i]["findings_json"], f"Findings diverged on run {i + 1}"
