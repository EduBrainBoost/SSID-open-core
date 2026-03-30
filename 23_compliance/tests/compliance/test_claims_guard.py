"""Tests for claims_guard compliance rule.
Source: 23_compliance/policies/claims_guard.rego
Phase 4 — A02_A03_COMPLETION
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_claims_guard import validate_claims_guard


def test_claims_guard_pass_empty():
    """Test that empty scanned files passes claims_guard."""
    data = {"scanned_files": [], "evidence_flags": []}
    assert validate_claims_guard(data) is True


def test_claims_guard_pass_clean_content():
    """Test that content without forbidden claims passes."""
    data = {
        "scanned_files": [{"path": "docs/readme.md", "content": "Normal documentation text."}],
        "evidence_flags": [],
    }
    assert validate_claims_guard(data) is True


def test_claims_guard_fail_forbidden_claim():
    """Test that forbidden claim without evidence fails."""
    data = {
        "scanned_files": [
            {"path": "docs/status.md", "content": "System is INTERFEDERATION_ACTIVE now."}
        ],
        "evidence_flags": [],
    }
    assert validate_claims_guard(data) is False


def test_claims_guard_pass_claim_with_evidence():
    """Test that forbidden claim WITH verified evidence passes."""
    data = {
        "scanned_files": [
            {"path": "docs/status.md", "content": "System is INTERFEDERATION_ACTIVE now."}
        ],
        "evidence_flags": [{"claim": "INTERFEDERATION_ACTIVE", "verified": True}],
    }
    assert validate_claims_guard(data) is True


def test_claims_guard_fail_unverified_evidence():
    """Test that forbidden claim with unverified evidence still fails."""
    data = {
        "scanned_files": [
            {"path": "docs/status.md", "content": "System is EXECUTION_READY."}
        ],
        "evidence_flags": [{"claim": "EXECUTION_READY", "verified": False}],
    }
    assert validate_claims_guard(data) is False


def test_claims_guard_fail_on_none():
    """Test that None input fails claims_guard."""
    assert validate_claims_guard(None) is False


def test_claims_guard_fail_on_non_dict():
    """Test that non-dict input fails claims_guard."""
    assert validate_claims_guard("string") is False


def test_claims_guard_contract_exists():
    """Test that contract file exists for claims_guard."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/claims_guard.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
