"""Tests for structure_policy compliance rule.
Source: 23_compliance/policies/structure/structure_policy.rego
Phase 4 — A02_A03_COMPLETION
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_structure_policy import validate_structure_policy


def test_structure_policy_pass_valid_paths():
    """Test that valid SSID shard paths pass structure_policy."""
    data = {
        "file_paths": [
            "23_compliance/policies/sot_policy.rego",
            "12_tooling/cli/run_gate.py",
            "03_core/validators/validator.py",
        ],
        "files": [
            {"name": "sot_policy.rego", "path": "23_compliance/policies/sot_policy.rego"},
            {"name": "run_gate.py", "path": "12_tooling/cli/run_gate.py"},
        ],
    }
    assert validate_structure_policy(data) is True


def test_structure_policy_pass_empty():
    """Test that empty input passes structure_policy."""
    data = {"file_paths": [], "files": []}
    assert validate_structure_policy(data) is True


def test_structure_policy_fail_invalid_path():
    """Test that a root-level file fails structure_policy."""
    data = {
        "file_paths": ["random_file.py"],
        "files": [],
    }
    assert validate_structure_policy(data) is False


def test_structure_policy_pass_github_paths():
    """Test that .github/ paths pass (known top-level)."""
    data = {
        "file_paths": [".github/workflows/ci.yaml"],
        "files": [],
    }
    assert validate_structure_policy(data) is True


def test_structure_policy_pass_repair_evidence():
    """Test that repair-run-evidence/ paths pass."""
    data = {
        "file_paths": ["repair-run-evidence/report.json"],
        "files": [],
    }
    assert validate_structure_policy(data) is True


def test_structure_policy_fail_on_none():
    """Test that None input fails."""
    assert validate_structure_policy(None) is False


def test_structure_policy_contract_exists():
    """Test that contract file exists for structure_policy."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/structure_policy.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
