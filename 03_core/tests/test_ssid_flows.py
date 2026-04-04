"""Tests for P4.1 + P4.2: ssid_flows.py — PolicyEnforcer injection + Evidence contract."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Ensure 03_core is on the path
_CORE = Path(__file__).resolve().parent.parent
_REPO = _CORE.parent
sys.path.insert(0, str(_CORE))
sys.path.insert(0, str(_REPO / "08_identity_score"))
sys.path.insert(0, str(_REPO / "02_audit_logging"))

from fee_distribution_engine import FeeParticipant, ParticipantRole
from flow_evidence import FlowEvidence
from governance_reward_engine import GovernanceActivity, GovernanceActivityType, GovernanceParticipant
from license_fee_splitter import LicenseType
from policy_enforcer import PolicyViolationError
from reward_handler import RewardAction, RewardEvent
from ssid_flows import (
    LicenseFeeFlowResult,
    RewardGovernanceFlowResult,
    SubscriptionFlowResult,
    run_license_fee_flow,
    run_reward_governance_flow,
    run_subscription_revenue_flow,
)
from subscription_revenue_distributor import RevenueParticipant, SubscriptionTier

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_revenue_participants():
    return [
        RevenueParticipant("p1", service_units=60),
        RevenueParticipant("p2", service_units=40),
    ]


def _make_fee_participants():
    return [
        FeeParticipant("v1", ParticipantRole.VALIDATOR, 0.9),
        FeeParticipant("v2", ParticipantRole.VALIDATOR, 0.8),
    ]


def _make_governance_participants():
    return [
        GovernanceParticipant("alice", [GovernanceActivity(GovernanceActivityType.VOTE)]),
        GovernanceParticipant("bob", [GovernanceActivity(GovernanceActivityType.PROPOSAL)]),
    ]


def _make_reward_events():
    return [
        RewardEvent("evt-1", "alice", RewardAction.GOVERNANCE_VOTE, 0.9),
        RewardEvent("evt-2", "bob", RewardAction.DATA_PROVISION, 0.75, quantity=3),
    ]


# ---------------------------------------------------------------------------
# TestSubscriptionFlow
# ---------------------------------------------------------------------------


class TestSubscriptionFlow:
    def test_returns_flow_result_with_evidence(self):
        result = run_subscription_revenue_flow(
            gross_revenue=Decimal("1000.00"),
            participants=_make_revenue_participants(),
            tier=SubscriptionTier.PROFESSIONAL,
        )
        assert isinstance(result, SubscriptionFlowResult)
        assert isinstance(result.evidence, FlowEvidence)
        assert result.distribution is not None

    def test_evidence_has_required_fields(self):
        result = run_subscription_revenue_flow(
            gross_revenue=Decimal("500.00"),
            participants=_make_revenue_participants(),
            tier=SubscriptionTier.STARTER,
        )
        ev = result.evidence
        assert ev.flow_id
        assert ev.flow_name == "subscription_revenue"
        assert ev.input_hash
        assert ev.output_hash
        assert isinstance(ev.policy_decisions, list)
        assert ev.proof_hash is not None and len(ev.proof_hash) == 64
        assert ev.determinism_hash

    def test_policy_denial_raises(self):
        with pytest.raises(PolicyViolationError):
            run_subscription_revenue_flow(
                gross_revenue=Decimal("-100.00"),
                participants=_make_revenue_participants(),
            )

    def test_evidence_deny_on_policy_failure(self):
        # Negative revenue triggers PolicyViolationError — confirm it propagates
        with pytest.raises(PolicyViolationError):
            run_subscription_revenue_flow(
                gross_revenue=Decimal("-1.00"),
                participants=_make_revenue_participants(),
            )


# ---------------------------------------------------------------------------
# TestLicenseFeeFlow
# ---------------------------------------------------------------------------


class TestLicenseFeeFlow:
    def test_returns_flow_result(self):
        result = run_license_fee_flow(
            amount=Decimal("200.00"),
            license_type=LicenseType.COMMERCIAL,
            fee_participants=_make_fee_participants(),
        )
        assert isinstance(result, LicenseFeeFlowResult)
        assert result.split is not None
        assert isinstance(result.evidence, FlowEvidence)

    def test_evidence_fields_complete(self):
        result = run_license_fee_flow(
            amount=Decimal("100.00"),
            license_type=LicenseType.STANDARD,
            fee_participants=_make_fee_participants(),
        )
        d = result.evidence.to_dict()
        required_keys = {
            "flow_id",
            "flow_name",
            "input_hash",
            "output_hash",
            "policy_decisions",
            "allow_or_deny",
            "proof_hash",
            "timestamp_utc",
            "module_versions",
            "determinism_hash",
        }
        assert required_keys.issubset(d.keys())

    def test_validator_share_distributed(self):
        from license_fee_splitter import SplitRecipient

        result = run_license_fee_flow(
            amount=Decimal("400.00"),
            license_type=LicenseType.ENTERPRISE,
            fee_participants=_make_fee_participants(),
        )
        validator_share = result.split.allocations[SplitRecipient.VALIDATOR]
        assert validator_share > Decimal("0")
        assert result.validator_distribution.allocations

    def test_evidence_json_serializable(self):
        result = run_license_fee_flow(
            amount=Decimal("150.00"),
            license_type=LicenseType.BASIC,
            fee_participants=_make_fee_participants(),
        )
        json_str = result.evidence.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["flow_name"] == "license_fee"


# ---------------------------------------------------------------------------
# TestRewardGovernanceFlow
# ---------------------------------------------------------------------------


class TestRewardGovernanceFlow:
    def test_returns_flow_result(self):
        result = run_reward_governance_flow(
            reward_events=_make_reward_events(),
            governance_pool=Decimal("500.00"),
            governance_participants=_make_governance_participants(),
        )
        assert isinstance(result, RewardGovernanceFlowResult)
        assert result.rewards is not None
        assert result.governance is not None
        assert isinstance(result.evidence, FlowEvidence)

    def test_evidence_proof_hash_present(self):
        result = run_reward_governance_flow(
            reward_events=_make_reward_events(),
            governance_pool=Decimal("1000.00"),
            governance_participants=_make_governance_participants(),
        )
        ph = result.evidence.proof_hash
        assert ph is not None
        assert len(ph) == 64
        # SHA-256 hex is all hex characters
        int(ph, 16)  # raises ValueError if not valid hex

    def test_policy_deny_no_participants(self):
        with pytest.raises(PolicyViolationError):
            run_reward_governance_flow(
                reward_events=_make_reward_events(),
                governance_pool=Decimal("100.00"),
                governance_participants=[],  # empty → MIN_PARTICIPANTS violation
            )

    def test_evidence_determinism_hash_stable(self):
        """Same inputs must produce same determinism_hash."""
        kwargs = dict(
            reward_events=_make_reward_events(),
            governance_pool=Decimal("250.00"),
            governance_participants=_make_governance_participants(),
            flow_id="deterministic-test-id",
        )
        r1 = run_reward_governance_flow(**kwargs)
        r2 = run_reward_governance_flow(**kwargs)
        assert r1.evidence.determinism_hash == r2.evidence.determinism_hash
