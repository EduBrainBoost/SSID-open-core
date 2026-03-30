"""Tests for sot_policy compliance rule.
Source: 23_compliance/policies/sot/sot_policy.rego
Phase 4 — A02_A03_COMPLETION
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_sot_policy import validate_sot_policy


def test_sot_policy_pass_root24_lock():
    """Test that valid ROOT-24-LOCK context passes sot_policy."""
    data = {"security_context": "ROOT-24-LOCK", "changed_files": []}
    assert validate_sot_policy(data) is True


def test_sot_policy_fail_missing_lock():
    """Test that missing ROOT-24-LOCK context fails."""
    data = {"security_context": "USER", "changed_files": []}
    assert validate_sot_policy(data) is False


def test_sot_policy_fail_no_context():
    """Test that absent security_context fails."""
    data = {"changed_files": []}
    assert validate_sot_policy(data) is False


def test_sot_policy_pass_allowed_path():
    """Test that allowed path change with ROOT-24-LOCK passes."""
    data = {
        "security_context": "ROOT-24-LOCK",
        "changed_files": [{"path": "23_compliance/policies/sot/sot_policy.rego"}],
        "allowed_paths": ["23_compliance/"],
    }
    assert validate_sot_policy(data) is True


def test_sot_policy_fail_write_gate_violation():
    """Test WRITE_GATE_VIOLATION: path not in allowlist."""
    data = {
        "security_context": "ROOT-24-LOCK",
        "changed_files": [{"path": "03_core/dispatcher.py"}],
        "allowed_paths": ["23_compliance/"],
    }
    assert validate_sot_policy(data) is False


def test_sot_policy_fail_on_none():
    """Test that None input fails."""
    assert validate_sot_policy(None) is False


def test_sot_policy_contract_exists():
    """Test that contract file exists for sot_policy."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/sot_policy.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
