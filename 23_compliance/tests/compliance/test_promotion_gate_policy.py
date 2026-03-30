"""Tests for promotion_gate_policy compliance rule.
Source: 23_compliance/policies/registry/promotion_gate_policy.rego
Phase 4 — A02_A03_COMPLETION
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_promotion_gate_policy import validate_promotion_gate_policy


VALID_DATA = {
    "canonical_artifacts": [
        {
            "name": "artifact_a",
            "path": "public/artifact_a.py",
            "hash_sha256": "abc123",
            "evidence_ref": "ev-001",
            "source_of_truth_ref": "sot-001",
            "on_disk": True,
        }
    ],
    "derivative_artifacts": [
        {
            "name": "artifact_a",
            "path": "public/artifact_a.py",
            "hash_sha256": "abc123",
            "on_disk": True,
        }
    ],
    "export_scopes": ["public/"],
    "forbidden_patterns": ["private/"],
}


def test_promotion_gate_pass_valid():
    """Test that valid promotion data passes."""
    assert validate_promotion_gate_policy(VALID_DATA) is True


def test_promotion_gate_fail_missing_derivative():
    """Test PROMO_ENFORCE_001: canonical on_disk with no derivative."""
    data = {
        "canonical_artifacts": [
            {"name": "a", "path": "public/a.py", "hash_sha256": "x", "on_disk": True}
        ],
        "derivative_artifacts": [],
        "export_scopes": ["public/"],
        "forbidden_patterns": [],
    }
    assert validate_promotion_gate_policy(data) is False


def test_promotion_gate_fail_unexpected_derivative():
    """Test PROMO_ENFORCE_002: derivative with no canonical source."""
    data = {
        "canonical_artifacts": [],
        "derivative_artifacts": [
            {"name": "b", "path": "public/b.py", "hash_sha256": "y", "on_disk": True}
        ],
        "export_scopes": ["public/"],
        "forbidden_patterns": [],
    }
    assert validate_promotion_gate_policy(data) is False


def test_promotion_gate_fail_hash_drift():
    """Test PROMO_ENFORCE_004: hash drift between canonical and derivative."""
    data = {
        "canonical_artifacts": [
            {"name": "a", "path": "public/a.py", "hash_sha256": "hash1", "on_disk": True}
        ],
        "derivative_artifacts": [
            {"name": "a", "path": "public/a.py", "hash_sha256": "hash2", "on_disk": True}
        ],
        "export_scopes": ["public/"],
        "forbidden_patterns": [],
    }
    assert validate_promotion_gate_policy(data) is False


def test_promotion_gate_fail_forbidden_pattern():
    """Test PROMO_ENFORCE_003: derivative matches forbidden pattern."""
    data = {
        "canonical_artifacts": [
            {"name": "priv", "path": "private/secret.py", "hash_sha256": "x", "on_disk": True}
        ],
        "derivative_artifacts": [
            {"name": "priv", "path": "private/secret.py", "hash_sha256": "x", "on_disk": True}
        ],
        "export_scopes": ["private/"],
        "forbidden_patterns": ["private/"],
    }
    assert validate_promotion_gate_policy(data) is False


def test_promotion_gate_fail_on_none():
    """Test that None input fails."""
    assert validate_promotion_gate_policy(None) is False


def test_promotion_gate_contract_exists():
    """Test that contract file exists for promotion_gate_policy."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/promotion_gate_policy.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
