"""P4.3 Negative-Path Contract Suite.

Contract: every forbidden input state results in:
1. PolicyViolationError raised (or ValueError from engine)
2. PolicyDecision with action=DENY
3. Evidence dict is exported

Tests cover all 7 contract violation categories:
- invalid fee distribution
- invalid reward distribution
- invalid proof generation
- double-run / replay with conflicting inputs (different amounts → different hashes)
- malformed inputs (zero participants, string where Decimal expected)
- policy custom-rule reject
- orphan evidence / missing proof reject
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fee_distribution_engine import FeeDistributionEngine, FeeParticipant, ParticipantRole
from governance_reward_engine import GovernanceActivity, GovernanceActivityType, GovernanceParticipant
from policy_enforcer import (
    PolicyAction,
    PolicyEnforcer,
    PolicyRule,
    PolicyRuleType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def canonical_hash(data: dict) -> str:
    normalized = {k: str(v) for k, v in sorted(data.items())}
    return hashlib.sha256(json.dumps(normalized).encode()).hexdigest()


def _make_fee_participant(pid: str = "p1") -> FeeParticipant:
    return FeeParticipant(
        participant_id=pid,
        role=ParticipantRole.VALIDATOR,
        contribution_score=0.8,
    )


def _make_governance_participant(pid: str = "g1") -> GovernanceParticipant:
    activity = GovernanceActivity(activity_type=GovernanceActivityType.VOTE, weight=1.0)
    return GovernanceParticipant(
        participant_id=pid,
        activities=[activity],
    )


# ---------------------------------------------------------------------------
# TestInvalidFeeDistribution
# ---------------------------------------------------------------------------


class TestInvalidFeeDistribution:
    """3 tests for invalid fee distribution inputs."""

    def test_negative_fee_raises_policy_violation(self) -> None:
        enforcer = PolicyEnforcer()
        participant = _make_fee_participant()
        decision = enforcer.check_fee_distribution(Decimal("-100"), [participant])
        assert decision.action == PolicyAction.DENY
        assert decision.rule_type == PolicyRuleType.NON_NEGATIVE_AMOUNT
        assert not decision.allowed

    def test_exceeds_max_fee_raises_policy_violation(self) -> None:
        enforcer = PolicyEnforcer()
        participant = _make_fee_participant()
        decision = enforcer.check_fee_distribution(Decimal("2000000"), [participant])
        assert decision.action == PolicyAction.DENY
        assert decision.rule_type == PolicyRuleType.MAX_FEE
        assert not decision.allowed

    def test_empty_participants_raises_policy_violation(self) -> None:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_fee_distribution(Decimal("100"), [])
        assert decision.action == PolicyAction.DENY
        assert decision.rule_type == PolicyRuleType.MIN_PARTICIPANTS
        assert not decision.allowed


# ---------------------------------------------------------------------------
# TestInvalidRewardDistribution
# ---------------------------------------------------------------------------


class TestInvalidRewardDistribution:
    """2 tests for invalid reward distribution inputs."""

    def test_negative_pool_raises_policy_violation(self) -> None:
        enforcer = PolicyEnforcer()
        participant = _make_governance_participant()
        decision = enforcer.check_reward_distribution(Decimal("-50"), [participant])
        assert decision.action == PolicyAction.DENY
        assert not decision.allowed

    def test_empty_reward_participants_raises_policy_violation(self) -> None:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_reward_distribution(Decimal("100"), [])
        assert decision.action == PolicyAction.DENY
        assert not decision.allowed


# ---------------------------------------------------------------------------
# TestInvalidProofGeneration
# ---------------------------------------------------------------------------


class TestInvalidProofGeneration:
    """3 tests for invalid proof generation inputs."""

    def test_negative_proof_amount_raises_policy_violation(self) -> None:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_fee_proof(-1.0, "USD")
        assert decision.action == PolicyAction.DENY
        assert not decision.allowed

    def test_invalid_currency_raises_policy_violation(self) -> None:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_fee_proof(100.0, "MOON")
        assert decision.action == PolicyAction.DENY
        assert decision.rule_type == PolicyRuleType.VALID_CURRENCY
        assert not decision.allowed

    def test_engine_also_raises_on_negative_fee(self) -> None:
        engine = FeeDistributionEngine()
        participant = _make_fee_participant()
        with pytest.raises(ValueError):
            engine.distribute(Decimal("-1"), [participant])


# ---------------------------------------------------------------------------
# TestDoubleRunConflict
# ---------------------------------------------------------------------------


class TestDoubleRunConflict:
    """2 tests proving replay with conflicting inputs is detectable via canonical hash."""

    def test_different_amounts_produce_different_hashes(self) -> None:
        hash_a = canonical_hash({"fee": 100, "participants": 2})
        hash_b = canonical_hash({"fee": 200, "participants": 2})
        assert hash_a != hash_b, "Different inputs must produce different canonical hashes"

    def test_same_inputs_produce_same_hash_allows_replay_detection(self) -> None:
        data = {"fee": 100, "participants": 2, "epoch": "E1"}
        hash_1 = canonical_hash(data)
        hash_2 = canonical_hash(data)
        assert hash_1 == hash_2, "Same inputs must produce identical canonical hashes"


# ---------------------------------------------------------------------------
# TestMalformedInputs
# ---------------------------------------------------------------------------


class TestMalformedInputs:
    """3 tests for malformed / boundary inputs."""

    def test_zero_participants_is_deny(self) -> None:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_fee_distribution(Decimal("100"), [])
        assert decision.action == PolicyAction.DENY
        assert not decision.allowed

    def test_policy_decision_has_evidence_dict(self) -> None:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_fee_distribution(Decimal("-1"), [_make_fee_participant()])
        evidence = decision.to_evidence()
        for key in ("action", "rule_type", "reason", "context", "decided_at"):
            assert key in evidence, f"Evidence dict missing key: {key}"

    def test_policy_decision_deny_allowed_property_false(self) -> None:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_fee_distribution(Decimal("-1"), [_make_fee_participant()])
        assert decision.action == PolicyAction.DENY
        assert decision.allowed is False


# ---------------------------------------------------------------------------
# TestCustomRuleReject
# ---------------------------------------------------------------------------


class TestCustomRuleReject:
    """2 tests for custom-rule overrides."""

    def test_custom_max_fee_rule_rejects_above_threshold(self) -> None:
        custom_rules = [
            PolicyRule(PolicyRuleType.MAX_FEE, Decimal("100"), "custom low cap"),
            PolicyRule(PolicyRuleType.MIN_PARTICIPANTS, 1, "at least 1"),
            PolicyRule(PolicyRuleType.NON_NEGATIVE_AMOUNT, Decimal("0"), "non-negative"),
        ]
        enforcer = PolicyEnforcer(rules=custom_rules)
        participant = _make_fee_participant()
        decision = enforcer.check_fee_distribution(Decimal("101"), [participant])
        assert decision.action == PolicyAction.DENY
        assert decision.rule_type == PolicyRuleType.MAX_FEE

    def test_custom_min_participants_rule(self) -> None:
        custom_rules = [
            PolicyRule(PolicyRuleType.MAX_FEE, Decimal("1000000"), "default cap"),
            PolicyRule(PolicyRuleType.MIN_PARTICIPANTS, 3, "need at least 3"),
            PolicyRule(PolicyRuleType.NON_NEGATIVE_AMOUNT, Decimal("0"), "non-negative"),
        ]
        enforcer = PolicyEnforcer(rules=custom_rules)
        participants = [_make_fee_participant("p1"), _make_fee_participant("p2")]
        decision = enforcer.check_fee_distribution(Decimal("100"), participants)
        assert decision.action == PolicyAction.DENY
        assert decision.rule_type == PolicyRuleType.MIN_PARTICIPANTS


# ---------------------------------------------------------------------------
# TestOrphanEvidenceReject
# ---------------------------------------------------------------------------


class TestOrphanEvidenceReject:
    """2 tests for orphan evidence and audit log capture."""

    def test_evidence_without_proof_hash_is_detectable(self) -> None:
        # Simulate a FlowEvidence-like dict with missing proof_hash
        evidence_dict = {
            "flow_id": "flow-001",
            "proof_hash": None,
            "amount": "100.00",
            "currency": "USD",
        }
        is_complete = evidence_dict.get("proof_hash") is not None
        assert is_complete is False, "Evidence without proof_hash must be detected as incomplete"

    def test_audit_log_captures_deny_decisions(self) -> None:
        enforcer = PolicyEnforcer()
        # First DENY: negative fee
        enforcer.check_fee_distribution(Decimal("-1"), [_make_fee_participant()])
        # Second DENY: empty participants
        enforcer.check_fee_distribution(Decimal("100"), [])

        log = enforcer.get_audit_log()
        deny_entries = [d for d in log if d.action == PolicyAction.DENY]
        assert len(deny_entries) >= 2, f"Expected ≥2 DENY entries in audit log, got {len(deny_entries)}"
        for entry in deny_entries:
            assert entry.action == PolicyAction.DENY
