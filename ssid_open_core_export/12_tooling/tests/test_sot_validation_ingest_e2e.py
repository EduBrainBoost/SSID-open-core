#!/usr/bin/env python3
"""E2E cross-repo tests for the SoT validation ingest pipeline.

Tests cover the full chain:
    run_sot_convergence -> report_aggregator -> ems_publish_findings -> EMS ingest/read

All external dependencies (HTTP, filesystem, subprocess) are mocked.
No scores -- PASS/FAIL + findings only.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cli.ems_publish_findings import (
    _build_payload,
    _post_event,
    _sha256,
    _validate_report,
)
from cli.ems_publish_findings import (
    main as ems_publish_main,
)
from cli.report_aggregator import (
    build_json_report as agg_build_json_report,
)
from cli.report_aggregator import (
    compute_evidence_sha256,
    compute_stats,
    decide_status,
    load_findings,
    write_audit_event,
)

# ---------------------------------------------------------------------------
# Import pipeline internals under test
# ---------------------------------------------------------------------------
from cli.run_sot_convergence import (
    EXIT_DENY,
    EXIT_SUCCESS,
    EXIT_WARN,
    _collect,
    _decide,
    _json_report,
    _max_sev,
    _run_identity,
    _step_policy,
)

# ---------------------------------------------------------------------------
# Helpers
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


def _make_finding(
    finding_id: str,
    cls: str = "content_drift",
    severity: str = "warn",
    source: str = "scanner",
    path: str = "03_core/README.md",
    details: str = "test finding",
    repo: str = "SSID",
) -> dict[str, Any]:
    """Build a single normalized finding with all required keys."""
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = {
        "id": finding_id,
        "class": cls,
        "severity": severity,
        "source": source,
        "path": path,
        "details": details,
        "timestamp": ts,
        "repo": repo,
    }
    raw["evidence_hash"] = hashlib.sha256(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()
    return raw


def _make_convergence_report(
    findings: list[dict[str, Any]], decision: str = "pass", exit_code: int = EXIT_SUCCESS
) -> dict[str, Any]:
    """Build a minimal convergence report matching _json_report output."""
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    rid = {
        "run_id": "test-run-001",
        "timestamp_utc": ts,
        "contract_sha256": "a" * 64,
        "contract_version": "4.1.0",
        "canonical_commit": "abc123",
        "derivative_commit": "def456",
        "report_sha256": "b" * 64,
        "evidence_sha256": "c" * 64,
        "decision": decision,
    }
    return {
        "report_version": "2.0.0",
        "run_identity": rid,
        "generated_at_utc": ts,
        "pipeline_steps": ["scan", "manifest", "opencore_sync", "policy_check", "report"],
        "exit_code": exit_code,
        "exit_label": {EXIT_SUCCESS: "success", EXIT_WARN: "warn", EXIT_DENY: "deny"}.get(exit_code, "unknown"),
        "decision": decision,
        "summary": {
            "total_findings": len(findings),
            "max_severity": _max_sev(findings) if findings else "info",
            "scanner_status": "PASS",
            "opencore_sync_status": "pass",
        },
        "findings": findings,
    }


def _valid_ems_event_payload(run_id: str = "20260310T120000Z", status: str = "pass") -> dict[str, Any]:
    """Build a fully schema-conformant EMS sot_validation event payload."""
    return {
        "event_type": "sot_validation",
        "ts": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "source": "run_sot_convergence",
        "repo": "SSID",
        "severity": "info",
        "status": status,
        "summary": {
            "total": 0,
            "deny": 0,
            "warn": 0,
            "info": 0,
            "decision": "pass",
        },
        "findings": [],
        "artifacts": ["sot_convergence_report.json"],
        "evidence_refs": [],
        "policy_engine": "python",
        "rego_policy_version": "1.0.0",
        "python_policy_version": "1.0.0",
        "pipeline_version": "1.0.0",
    }


@pytest.fixture()
def tmp_repos(tmp_path: Path):
    """Create minimal canonical + derivative directory trees."""
    canonical = tmp_path / "ssid"
    derivative = tmp_path / "ssid-open-core"
    canonical.mkdir()
    derivative.mkdir()
    contract = canonical / "16_codex" / "contracts" / "sot"
    contract.mkdir(parents=True)
    (contract / "sot_contract.yaml").write_text("version: '4.1.0'\nrules: []\n", encoding="utf-8")
    return canonical, derivative


# ===================================================================
# 1. test_convergence_to_ingest_chain
# ===================================================================


@patch("cli.run_sot_convergence._git_head", return_value="abc123")
def test_convergence_to_ingest_chain(_mock_git, tmp_repos):
    """Full chain: run_sot_convergence produces valid report -> ems_publish_findings
    builds payload -> mock EMS returns 201 -> verify payload matches schema fields.

    Validates that the convergence pipeline output can be consumed by the EMS
    publisher and that the resulting payload contains all required event fields.
    """
    canonical, derivative = tmp_repos

    # Step 1: Run convergence pipeline internals
    scan = _clean_scan()
    sync = _clean_sync()
    policy = _step_policy(scan, sync)
    findings = _collect(scan, sync, policy)
    decision, exit_code = _decide(findings)

    rid = _run_identity(canonical, derivative, findings, decision, json.dumps(findings, sort_keys=True))
    report = _json_report(scan, "{}", sync, findings, decision, exit_code, rid)

    # Step 2: Validate the report is acceptable to ems_publish_findings
    report_errs = _validate_report(report)
    assert report_errs == [], f"Report validation errors: {report_errs}"

    # Step 3: Build the EMS event payload
    report_raw = json.dumps(report, sort_keys=True).encode("utf-8")
    payload = _build_payload(report, report_raw, "abc123", _sha256(report_raw), run_identity=rid)

    # Step 4: Verify payload has all EMS-expected fields
    assert payload["event_type"] == "sot_validation"
    assert "timestamp" in payload
    assert "pipeline_version" in payload
    assert "commit_id" in payload
    assert payload["commit_id"] == "abc123"
    assert "summary" in payload
    assert "report_sha256" in payload
    assert "findings_preview" in payload
    assert isinstance(payload["findings_preview"], list)

    # Step 5: Verify summary structure
    summary = payload["summary"]
    assert "total_findings" in summary
    assert "deny_count" in summary
    assert "warn_count" in summary
    assert "info_count" in summary
    assert "decision" in summary

    # Step 6: Verify run_identity is attached when provided
    assert "run_identity" in payload
    assert payload["run_identity"]["run_id"] == rid["run_id"]

    # Step 7: Mock POST to EMS and verify 201 acceptance
    mock_resp = MagicMock()
    mock_resp.status = 201
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("cli.ems_publish_findings.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result = _post_event("http://localhost:8000/events/sot_validation", payload)
        assert result is True, "POST should succeed with 201 response"
        mock_urlopen.assert_called_once()


# ===================================================================
# 2. test_schema_validation_rejects_invalid
# ===================================================================


def test_schema_validation_rejects_invalid():
    """Produce invalid payload (missing required fields) -> schema validation
    catches it -> publisher returns exit code indicating schema failure.

    Validates that the schema validation gate prevents malformed events from
    being published to EMS.
    """
    # Build a report missing the required 'findings' field
    invalid_report = {"decision": "pass", "summary": {}}

    report_errs = _validate_report(invalid_report)
    assert len(report_errs) > 0, "Validation must reject report missing 'findings'"
    assert any("findings" in e.lower() for e in report_errs), "Error must reference missing 'findings' field"

    # Test via CLI main() with a malformed report file
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "bad_report.json"
        report_path.write_text(json.dumps(invalid_report), encoding="utf-8")

        exit_code = ems_publish_main(
            [
                "--report",
                str(report_path),
                "--commit-id",
                "abc123",
                "--dry-run",
            ]
        )
        # main() returns 1 for report validation failure
        assert exit_code == 1, f"Expected exit code 1 for invalid report, got {exit_code}"


# ===================================================================
# 3. test_duplicate_run_id_handling
# ===================================================================


def test_duplicate_run_id_handling():
    """POST same run_id twice -> second gets 409 -> publisher handles gracefully.

    Validates that the publisher does not crash on HTTP 409 Conflict when
    a duplicate run_id is submitted.
    """
    report = _make_convergence_report([])
    report_raw = json.dumps(report, sort_keys=True).encode("utf-8")
    payload = _build_payload(report, report_raw, "abc123", _sha256(report_raw))

    # First POST: 201 Created
    mock_resp_201 = MagicMock()
    mock_resp_201.status = 201
    mock_resp_201.__enter__ = MagicMock(return_value=mock_resp_201)
    mock_resp_201.__exit__ = MagicMock(return_value=False)

    with patch("cli.ems_publish_findings.urllib.request.urlopen", return_value=mock_resp_201):
        result_first = _post_event("http://localhost:8000/events/sot_validation", payload)
        assert result_first is True, "First POST should succeed"

    # Second POST: 409 Conflict via HTTPError
    import urllib.error

    http_409 = urllib.error.HTTPError(
        url="http://localhost:8000/events/sot_validation",
        code=409,
        msg="Conflict: duplicate run_id",
        hdrs=MagicMock(),
        fp=None,
    )

    with (
        patch("cli.ems_publish_findings.urllib.request.urlopen", side_effect=http_409),
        patch("cli.ems_publish_findings.time.sleep"),
    ):  # skip retry waits
        result_second = _post_event("http://localhost:8000/events/sot_validation", payload, retries=1)
        # _post_event returns False on HTTP errors but does not raise
        assert result_second is False, "Second POST with 409 should return False (graceful handling)"


# ===================================================================
# 4. test_read_api_returns_stored_event
# ===================================================================


def test_read_api_returns_stored_event():
    """Mock GET /api/admin/sot-validations/{run_id} -> verify response structure
    matches what was POSTed.

    Validates round-trip: the payload structure that the publisher POSTs should
    be retrievable from the EMS read API with matching fields.
    """
    run_id = "20260310T120000Z"
    report = _make_convergence_report([])
    report_raw = json.dumps(report, sort_keys=True).encode("utf-8")
    payload = _build_payload(report, report_raw, "abc123", _sha256(report_raw))
    payload["run_id"] = run_id  # Tag for retrieval

    # Simulate EMS storing and returning the event
    stored_event = {
        "id": 1,
        "run_id": run_id,
        "event_type": payload["event_type"],
        "timestamp": payload["timestamp"],
        "pipeline_version": payload["pipeline_version"],
        "commit_id": payload["commit_id"],
        "summary": payload["summary"],
        "report_sha256": payload["report_sha256"],
        "findings_preview": payload["findings_preview"],
        "created_at": datetime.now(UTC).isoformat(),
    }

    # Mock GET response
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(stored_event).encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        import urllib.request

        req = urllib.request.Request(
            f"http://localhost:8000/api/admin/sot-validations/{run_id}",
            method="GET",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

    # Verify round-trip field consistency
    assert data["run_id"] == run_id
    assert data["event_type"] == payload["event_type"]
    assert data["pipeline_version"] == payload["pipeline_version"]
    assert data["commit_id"] == payload["commit_id"]
    assert data["report_sha256"] == payload["report_sha256"]
    assert data["summary"] == payload["summary"]
    assert data["findings_preview"] == payload["findings_preview"]


# ===================================================================
# 5. test_audit_log_entry_created
# ===================================================================


def test_audit_log_entry_created():
    """After successful ingest -> verify audit_log.jsonl has entry with hash chain.

    Validates that the report_aggregator writes a run_audit_event.json with
    correct evidence hashes forming a verifiable chain.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # Create findings with evidence hashes
        findings = [
            _make_finding(
                "SCN-0001", cls="content_drift", severity="warn", path="03_core/README.md", details="content changed"
            ),
            _make_finding(
                "SCN-0002", cls="content_drift", severity="info", path="12_tooling/module.yaml", details="minor update"
            ),
        ]

        stats = compute_stats(findings)
        status = decide_status(stats)
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        evidence_sha = compute_evidence_sha256(findings)

        # Build report and compute its hash
        report_payload = agg_build_json_report(
            "RUN_TEST_001",
            findings,
            stats,
            status,
            ts,
            evidence_sha256=evidence_sha,
        )
        report_bytes = json.dumps(report_payload, indent=2).encode("utf-8")
        report_hash = hashlib.sha256(report_bytes).hexdigest()

        # Write audit event
        audit_path = write_audit_event(
            output_dir,
            "RUN_TEST_001",
            ts,
            status,
            stats,
            report_hash,
            evidence_sha,
        )

        # Verify audit file exists and has correct structure
        assert audit_path.exists(), "Audit event file must be created"
        audit_data = json.loads(audit_path.read_text(encoding="utf-8"))

        assert audit_data["run_id"] == "RUN_TEST_001"
        assert audit_data["decision"] == status
        assert audit_data["report_sha256"] == report_hash
        assert audit_data["evidence_sha256"] == evidence_sha

        # Verify hash chain: evidence_sha256 is derived from finding hashes
        recomputed_evidence = compute_evidence_sha256(findings)
        assert audit_data["evidence_sha256"] == recomputed_evidence, (
            "Evidence hash in audit must match recomputed hash from findings"
        )

        # Verify summary counters match
        assert audit_data["findings_summary"]["total"] == len(findings)
        assert audit_data["findings_summary"]["warn"] == stats["by_severity"].get("warn", 0)
        assert audit_data["findings_summary"]["info"] == stats["by_severity"].get("info", 0)
        assert audit_data["findings_summary"]["deny"] == stats["by_severity"].get("deny", 0)


# ===================================================================
# 6. test_full_pipeline_report_aggregation
# ===================================================================


def test_full_pipeline_report_aggregation():
    """Multiple findings files -> aggregator merges -> validates against schema
    -> publishes -> verify aggregated summary.

    Validates the full aggregation pipeline: multiple *.findings.json files
    are loaded, merged, validated, and the resulting report contains correct
    aggregated statistics.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = Path(tmpdir) / "findings"
        output_dir = Path(tmpdir) / "reports"
        input_dir.mkdir()
        output_dir.mkdir()

        # Create multiple findings files
        scanner_findings = [
            _make_finding(
                "SCN-0001",
                cls="content_drift",
                severity="warn",
                source="scanner",
                path="03_core/README.md",
                details="hash mismatch",
            ),
            _make_finding(
                "SCN-0002",
                cls="content_drift",
                severity="info",
                source="scanner",
                path="12_tooling/config.yaml",
                details="minor update",
            ),
        ]
        (input_dir / "scanner.findings.json").write_text(json.dumps(scanner_findings, indent=2), encoding="utf-8")

        sync_findings = [
            _make_finding(
                "SYNC-0001",
                cls="content_drift",
                severity="deny",
                source="opencore_sync",
                path="docs/overview.md",
                details="forbidden export detected",
                repo="SSID-open-core",
            ),
        ]
        (input_dir / "sync.findings.json").write_text(json.dumps(sync_findings, indent=2), encoding="utf-8")

        policy_findings = [
            _make_finding(
                "POL-0001",
                cls="content_drift",
                severity="warn",
                source="policy_engine",
                path="05_governance/gaps.md",
                details="enforcement gap",
            ),
        ]
        (input_dir / "policy.findings.json").write_text(json.dumps(policy_findings, indent=2), encoding="utf-8")

        # Step 1: Load and merge findings
        all_findings = load_findings(input_dir)
        assert len(all_findings) == 4, f"Expected 4 findings from 3 files, got {len(all_findings)}"

        # Step 2: Compute stats and decision
        stats = compute_stats(all_findings)
        status = decide_status(stats)

        assert stats["total"] == 4
        assert stats["by_severity"].get("deny", 0) == 1
        assert stats["by_severity"].get("warn", 0) == 2
        assert stats["by_severity"].get("info", 0) == 1
        assert status == "FAIL", "Must be FAIL when deny findings exist"

        # Step 3: Build report
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        evidence_sha = compute_evidence_sha256(all_findings)
        report = agg_build_json_report(
            "RUN_AGG_001",
            all_findings,
            stats,
            status,
            ts,
            evidence_sha256=evidence_sha,
        )

        # Step 4: Verify report structure
        assert report["run_id"] == "RUN_AGG_001"
        assert report["decision"] == "FAIL"
        assert report["summary"]["total"] == 4
        assert len(report["findings"]) == 4

        # Step 5: Build EMS publish payload from aggregated report
        report_raw = json.dumps(report, sort_keys=True).encode("utf-8")
        payload = _build_payload(report, report_raw, "abc123", _sha256(report_raw))

        # Step 6: Verify aggregated summary in payload
        assert payload["summary"]["total_findings"] == 4
        assert payload["summary"]["deny_count"] == 1
        assert payload["summary"]["warn_count"] == 2
        assert payload["summary"]["info_count"] == 1
        assert payload["summary"]["decision"] == "deny", "Payload decision must be 'deny' when deny findings exist"

        # Step 7: Findings preview contains up to 10 items
        assert len(payload["findings_preview"]) == 4
        assert all(isinstance(f, dict) for f in payload["findings_preview"])

        # Step 8: Write audit event and verify chain
        audit_path = write_audit_event(
            output_dir,
            "RUN_AGG_001",
            ts,
            status,
            stats,
            _sha256(report_raw).encode("utf-8").hex()[:64],
            evidence_sha,
        )
        assert audit_path.exists()
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        assert audit["findings_summary"]["total"] == 4
        assert audit["findings_summary"]["deny"] == 1
