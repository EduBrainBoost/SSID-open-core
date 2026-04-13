"""Tests for interfederation_claims_guard compliance rule.
Source: 23_compliance/policies/interfederation/interfederation_claims_guard.rego
Phase 4 — A02_A03_COMPLETION
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../23_compliance/validators"))
from validate_interfederation_claims_guard import validate_interfederation_claims_guard


def test_interfederation_claims_guard_pass_empty():
    """Test that empty documents passes interfederation_claims_guard."""
    data = {"documents": [], "proof_snapshot": None}
    assert validate_interfederation_claims_guard(data) is True


def test_interfederation_claims_guard_pass_clean_content():
    """Test that content without forbidden claims passes."""
    data = {
        "documents": [{"path": "docs/report.md", "content": "Standard compliance report."}],
    }
    assert validate_interfederation_claims_guard(data) is True


def test_interfederation_claims_guard_fail_claim_no_proof():
    """Test that forbidden claim without proof snapshot fails."""
    data = {
        "documents": [{"path": "docs/status.md", "content": "interfederation active between systems."}],
    }
    assert validate_interfederation_claims_guard(data) is False


def test_interfederation_claims_guard_pass_claim_with_proof():
    """Test that forbidden claim with valid proof snapshot passes."""
    data = {
        "documents": [{"path": "docs/status.md", "content": "interfederation active between systems."}],
        "proof_snapshot": {
            "ssid_commit": "abc123",
            "opencore_commit": "def456",
            "file_hashes": {"file1.py": "sha256:aaa"},
        },
    }
    assert validate_interfederation_claims_guard(data) is True


def test_interfederation_claims_guard_fail_score_claim():
    """Test that numeric interfederation score claim fails regardless of proof."""
    data = {
        "documents": [{"path": "docs/score.md", "content": "50% interfed compliance achieved."}],
    }
    assert validate_interfederation_claims_guard(data) is False


def test_interfederation_claims_guard_fail_on_none():
    """Test that None input fails."""
    assert validate_interfederation_claims_guard(None) is False


def test_interfederation_claims_guard_contract_exists():
    """Test that contract file exists for interfederation_claims_guard."""
    contract_path = os.path.join(
        os.path.dirname(__file__),
        "../../contracts/interfederation_claims_guard.yaml",
    )
    assert os.path.exists(contract_path), f"Contract missing: {contract_path}"
