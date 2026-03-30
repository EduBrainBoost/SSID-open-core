"""Tests for sot_convergence_policy compliance rule.
Source: 23_compliance/policies/sot/sot_convergence_policy.rego
Phase 4 — A02_A03_COMPLETION
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_sot_convergence_policy import validate_sot_convergence_policy


def test_sot_convergence_pass():
    """Test that compliant convergence manifest passes."""
    data = {
        "repo_name": "SSID",
        "repo_role": "canonical",
        "status": "PASS",
        "missing_artifacts": [],
        "drift_findings": [],
        "export_ready": True,
    }
    assert validate_sot_convergence_policy(data) is True


def test_sot_convergence_fail_status():
    """Test D-001: overall status FAIL causes deny."""
    data = {
        "repo_name": "SSID",
        "repo_role": "canonical",
        "status": "FAIL",
        "missing_artifacts": [],
        "drift_findings": [],
    }
    assert validate_sot_convergence_policy(data) is False


def test_sot_convergence_fail_missing_artifacts():
    """Test D-002: canonical repo with missing artifacts fails."""
    data = {
        "repo_name": "SSID",
        "repo_role": "canonical",
        "status": "PASS",
        "missing_artifacts": ["file_a.py"],
        "drift_findings": [],
    }
    assert validate_sot_convergence_policy(data) is False


def test_sot_convergence_fail_protected_scope():
    """Test D-003: protected_scope_attempt finding causes deny."""
    data = {
        "repo_name": "SSID",
        "repo_role": "canonical",
        "status": "PASS",
        "missing_artifacts": [],
        "drift_findings": [
            {
                "path": "03_core/core.py",
                "detail": "unauthorized write",
                "severity": "high",
                "class": "protected_scope_attempt",
            }
        ],
    }
    assert validate_sot_convergence_policy(data) is False


def test_sot_convergence_fail_critical_drift():
    """Test D-004: critical-severity drift finding causes deny."""
    data = {
        "repo_name": "SSID",
        "repo_role": "canonical",
        "status": "PASS",
        "missing_artifacts": [],
        "drift_findings": [
            {
                "path": "some/file.py",
                "detail": "major hash mismatch",
                "severity": "critical",
                "class": "hash_drift",
            }
        ],
    }
    assert validate_sot_convergence_policy(data) is False


def test_sot_convergence_pass_derivative_not_export_ready():
    """Test W-002 (warn only): derivative not export-ready still passes validator."""
    data = {
        "repo_name": "SSID-open-core",
        "repo_role": "derivative",
        "status": "PASS",
        "missing_artifacts": [],
        "drift_findings": [],
        "export_ready": False,
    }
    # warn only — should still pass (no deny rule fires)
    assert validate_sot_convergence_policy(data) is True


def test_sot_convergence_fail_on_none():
    """Test that None input fails."""
    assert validate_sot_convergence_policy(None) is False


def test_sot_convergence_contract_exists():
    """Test that contract file exists for sot_convergence_policy."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/sot_convergence_policy.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
