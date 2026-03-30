"""Tests for PolicyEnforcer — P3.2 Runtime Policy Enforcement."""
from __future__ import annotations
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from policy_enforcer import (
    PolicyAction, PolicyDecision, PolicyEnforcer, PolicyRule,
    PolicyRuleType, PolicyViolationError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def enforcer() -> PolicyEnforcer:
    return PolicyEnforcer()


# ---------------------------------------------------------------------------
# Fee distribution tests
# ---------------------------------------------------------------------------

def test_fee_distribution_allow_valid(enforcer: PolicyEnforcer) -> None:
    """Positive fee with 1 participant should be ALLOW."""
    decision = enforcer.check_fee_distribution(Decimal("100"), ["alice"])
    assert decision.action == PolicyAction.ALLOW
    assert decision.allowed is True


def test_fee_distribution_deny_negative_fee(enforcer: PolicyEnforcer) -> None:
    """Negative fee must be DENY with NON_NEGATIVE_AMOUNT rule."""
    decision = enforcer.check_fee_distribution(Decimal("-1"), ["alice"])
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.NON_NEGATIVE_AMOUNT


def test_fee_distribution_deny_exceeds_max(enforcer: PolicyEnforcer) -> None:
    """Fee above 1_000_000 must be DENY with MAX_FEE rule."""
    decision = enforcer.check_fee_distribution(Decimal("1_000_001"), ["alice"])
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.MAX_FEE


def test_fee_distribution_deny_no_participants(enforcer: PolicyEnforcer) -> None:
    """Empty participant list must be DENY with MIN_PARTICIPANTS rule."""
    decision = enforcer.check_fee_distribution(Decimal("500"), [])
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.MIN_PARTICIPANTS


# ---------------------------------------------------------------------------
# Reward distribution tests
# ---------------------------------------------------------------------------

def test_reward_distribution_allow_valid(enforcer: PolicyEnforcer) -> None:
    """Non-negative pool with 1+ participant should be ALLOW."""
    decision = enforcer.check_reward_distribution(Decimal("1000"), ["bob"])
    assert decision.action == PolicyAction.ALLOW
    assert decision.allowed is True


def test_reward_distribution_deny_negative_pool(enforcer: PolicyEnforcer) -> None:
    """Negative pool must be DENY."""
    decision = enforcer.check_reward_distribution(Decimal("-5"), ["bob"])
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.MIN_POOL_AMOUNT


def test_reward_distribution_deny_no_participants(enforcer: PolicyEnforcer) -> None:
    """Empty participant list for reward must be DENY."""
    decision = enforcer.check_reward_distribution(Decimal("1000"), [])
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.MIN_PARTICIPANTS


# ---------------------------------------------------------------------------
# Fee proof tests
# ---------------------------------------------------------------------------

def test_fee_proof_allow_valid(enforcer: PolicyEnforcer) -> None:
    """Positive amount with known currency should be ALLOW."""
    decision = enforcer.check_fee_proof(50.0, "USD")
    assert decision.action == PolicyAction.ALLOW
    assert decision.allowed is True


def test_fee_proof_deny_negative_amount(enforcer: PolicyEnforcer) -> None:
    """Negative amount for fee proof must be DENY."""
    decision = enforcer.check_fee_proof(-1.0, "USD")
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.NON_NEGATIVE_AMOUNT


def test_fee_proof_deny_invalid_currency(enforcer: PolicyEnforcer) -> None:
    """Unknown currency must be DENY with VALID_CURRENCY rule."""
    decision = enforcer.check_fee_proof(10.0, "MOON")
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.VALID_CURRENCY


# ---------------------------------------------------------------------------
# Audit log tests
# ---------------------------------------------------------------------------

def test_audit_log_records_decisions(enforcer: PolicyEnforcer) -> None:
    """After 3 checks, audit log must have exactly 3 entries."""
    enforcer.check_fee_distribution(Decimal("100"), ["a"])
    enforcer.check_reward_distribution(Decimal("200"), ["b"])
    enforcer.check_fee_proof(5.0, "EUR")
    assert len(enforcer.get_audit_log()) == 3


def test_export_evidence_json_safe(enforcer: PolicyEnforcer) -> None:
    """export_evidence() must return dicts whose context values are all strings or None."""
    enforcer.check_fee_distribution(Decimal("100"), ["alice"])
    enforcer.check_fee_proof(-1.0, "USD")
    evidence_list = enforcer.export_evidence()
    assert len(evidence_list) == 2
    for entry in evidence_list:
        # Verify JSON serialisability
        json_str = __import__("json").dumps(entry)
        assert isinstance(json_str, str)
        # Context values must be strings
        for v in entry["context"].values():
            assert isinstance(v, str)
        # action and reason must be strings
        assert isinstance(entry["action"], str)
        assert isinstance(entry["reason"], str)
        # decided_at must be an ISO string
        assert isinstance(entry["decided_at"], str)


# ---------------------------------------------------------------------------
# PolicyViolationError tests
# ---------------------------------------------------------------------------

def test_policy_violation_error_has_decision(enforcer: PolicyEnforcer) -> None:
    """PolicyViolationError must carry the original PolicyDecision."""
    decision = enforcer.check_fee_distribution(Decimal("-1"), [])
    error = PolicyViolationError(decision)
    assert error.decision is decision
    assert "Policy violation" in str(error)


def test_decision_allowed_property() -> None:
    """ALLOW decision → .allowed is True; DENY → .allowed is False."""
    allow_d = PolicyDecision(PolicyAction.ALLOW, None, "ok", {})
    deny_d = PolicyDecision(PolicyAction.DENY, PolicyRuleType.MAX_FEE, "too big", {})
    assert allow_d.allowed is True
    assert deny_d.allowed is False


# ---------------------------------------------------------------------------
# Custom rules tests
# ---------------------------------------------------------------------------

def test_custom_rules_override_defaults() -> None:
    """Custom MAX_FEE of 100 should DENY a fee of 101."""
    custom_rules = [
        PolicyRule(PolicyRuleType.MAX_FEE, Decimal("100"), "tight cap"),
        PolicyRule(PolicyRuleType.MIN_PARTICIPANTS, 1, "min 1"),
        PolicyRule(PolicyRuleType.NON_NEGATIVE_AMOUNT, Decimal("0"), "non-neg"),
    ]
    enforcer = PolicyEnforcer(rules=custom_rules)
    decision = enforcer.check_fee_distribution(Decimal("101"), ["alice"])
    assert decision.action == PolicyAction.DENY
    assert decision.rule_type == PolicyRuleType.MAX_FEE
    # Default max (1_000_000) would have allowed 101 — confirm custom rule is active
    default_enforcer = PolicyEnforcer()
    default_decision = default_enforcer.check_fee_distribution(Decimal("101"), ["alice"])
    assert default_decision.action == PolicyAction.ALLOW
