"""Tests for registry_enforcement_policy compliance rule.
Source: 23_compliance/policies/registry/registry_enforcement_policy.rego
Phase 4 — A02_A03_COMPLETION
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_registry_enforcement_policy import validate_registry_enforcement_policy


VALID_DATA = {
    "artifacts": [
        {
            "name": "artifact_a",
            "path": "public/artifact_a.py",
            "hash_sha256": "abc123",
            "disk_hash": "abc123",
            "evidence_ref": "ev-001",
            "source_of_truth_ref": None,
            "on_disk": True,
        }
    ],
    "guards": [{"name": "guard_a", "unknown_value_behavior": "fail"}],
}


def test_registry_enforcement_pass_valid():
    """Test that valid registry data passes."""
    assert validate_registry_enforcement_policy(VALID_DATA) is True


def test_registry_enforcement_fail_unregistered():
    """Test REGISTRY_ENFORCE_001: on_disk artifact without hash."""
    data = {
        "artifacts": [
            {"name": "a", "path": "public/a.py", "on_disk": True, "evidence_ref": "ev-1"}
        ],
        "guards": [],
    }
    assert validate_registry_enforcement_policy(data) is False


def test_registry_enforcement_fail_hash_drift():
    """Test REGISTRY_ENFORCE_002: hash drift between disk and registry."""
    data = {
        "artifacts": [
            {
                "name": "a",
                "path": "public/a.py",
                "hash_sha256": "hash1",
                "disk_hash": "hash2",
                "evidence_ref": "ev-1",
                "on_disk": True,
            }
        ],
        "guards": [],
    }
    assert validate_registry_enforcement_policy(data) is False


def test_registry_enforcement_fail_missing_evidence():
    """Test REGISTRY_ENFORCE_003: artifact without evidence_ref."""
    data = {
        "artifacts": [
            {"name": "a", "path": "public/a.py", "hash_sha256": "h1", "on_disk": True}
        ],
        "guards": [],
    }
    assert validate_registry_enforcement_policy(data) is False


def test_registry_enforcement_fail_open_guard():
    """Test REGISTRY_ENFORCE_005: fail-open guard behavior."""
    data = {
        "artifacts": [
            {
                "name": "a",
                "path": "public/a.py",
                "hash_sha256": "h1",
                "evidence_ref": "ev-1",
                "on_disk": True,
            }
        ],
        "guards": [{"name": "guard_a", "unknown_value_behavior": "skip"}],
    }
    assert validate_registry_enforcement_policy(data) is False


def test_registry_enforcement_fail_on_none():
    """Test that None input fails."""
    assert validate_registry_enforcement_policy(None) is False


def test_registry_enforcement_contract_exists():
    """Test that contract file exists for registry_enforcement_policy."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/registry_enforcement_policy.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
