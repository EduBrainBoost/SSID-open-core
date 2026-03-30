"""Tests for sot_opencore_derivation_policy compliance rule.
Source: 23_compliance/policies/sot/sot_opencore_derivation_policy.rego
Phase 4 — A02_A03_COMPLETION
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_sot_opencore_derivation_policy import validate_sot_opencore_derivation_policy


def test_sot_opencore_derivation_pass():
    """Test that compliant export sync manifest passes."""
    data = {
        "canonical_repo": "SSID",
        "derivative_repo": "SSID-open-core",
        "status": "pass",
        "derivation_mode": "export",
        "registry_binding_status": "consistent",
        "findings": [],
        "allowed_exports": ["public/a.py"],
        "actual_exports": ["public/a.py"],
        "missing_exports": [],
        "forbidden_exports": [],
    }
    assert validate_sot_opencore_derivation_policy(data) is True


def test_sot_opencore_derivation_fail_status():
    """Test D-005: overall status fail causes deny."""
    data = {
        "canonical_repo": "SSID",
        "derivative_repo": "SSID-open-core",
        "status": "fail",
        "findings": [],
    }
    assert validate_sot_opencore_derivation_policy(data) is False


def test_sot_opencore_derivation_fail_forbidden_export():
    """Test D-001: forbidden_export finding causes deny."""
    data = {
        "status": "pass",
        "findings": [
            {"class": "forbidden_export", "detail": "leaked private key", "path": "private/key.pem", "severity": "critical"}
        ],
    }
    assert validate_sot_opencore_derivation_policy(data) is False


def test_sot_opencore_derivation_fail_hash_mismatch():
    """Test D-002: contract_hash_mismatch finding causes deny."""
    data = {
        "status": "pass",
        "findings": [
            {"class": "contract_hash_mismatch", "detail": "mismatch", "path": "public/a.py", "severity": "critical"}
        ],
    }
    assert validate_sot_opencore_derivation_policy(data) is False


def test_sot_opencore_derivation_fail_critical_stale_binding():
    """Test D-003: critical stale_derivative_binding causes deny."""
    data = {
        "status": "pass",
        "findings": [
            {"class": "stale_derivative_binding", "detail": "outdated", "path": "public/a.py", "severity": "critical"}
        ],
    }
    assert validate_sot_opencore_derivation_policy(data) is False


def test_sot_opencore_derivation_pass_noncritical_stale_binding():
    """Test W-004 (warn only): non-critical stale_derivative_binding passes validator."""
    data = {
        "status": "pass",
        "findings": [
            {"class": "stale_derivative_binding", "detail": "slightly outdated", "path": "public/a.py", "severity": "low"}
        ],
    }
    assert validate_sot_opencore_derivation_policy(data) is True


def test_sot_opencore_derivation_fail_on_none():
    """Test that None input fails."""
    assert validate_sot_opencore_derivation_policy(None) is False


def test_sot_opencore_derivation_contract_exists():
    """Test that contract file exists for sot_opencore_derivation_policy."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/sot_opencore_derivation_policy.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
