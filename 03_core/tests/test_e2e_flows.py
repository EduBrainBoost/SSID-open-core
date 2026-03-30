#!/usr/bin/env python3
"""P3.1 E2E integration tests — cross-module flows across all 8 productive core modules.

Covers:
  Flow 1: Subscription → Revenue Distribution → Fairness Audit
  Flow 2: License Fee → Split → Distribution → Proof
  Flow 3: Identity Score → Reward → Governance → Fairness

SoT v4.1.0 | ROOT-24-LOCK
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — make all modules importable from their canonical locations
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_core"))
sys.path.insert(0, str(_REPO_ROOT / "08_identity_score"))
sys.path.insert(0, str(_REPO_ROOT / "02_audit_logging"))

from fee_distribution_engine import (
    FeeDistributionEngine,
    FeeParticipant,
    ParticipantRole,
)
from subscription_revenue_distributor import (
    RevenueParticipant,
    SubscriptionRevenueDistributor,
    SubscriptionTier,
)
from fairness_engine import FairnessConstraint, FairnessEngine
from governance_reward_engine import (
    GovernanceActivity,
    GovernanceActivityType,
    GovernanceParticipant,
    GovernanceRewardEngine,
)
from license_fee_splitter import (
    LicenseFeeSplitter,
    LicenseType,
    SplitRecipient,
)
from reward_handler import (
    RewardAction,
    RewardEvent,
    RewardHandler,
)
from fee_proof_engine import FeeProofEngine


# ===========================================================================
# Flow 1: Subscription → Revenue Distribution → Fairness Audit
# ===========================================================================

class TestSubscriptionFairnessProofFlow:
    """Flow 1: SubscriptionRevenueDistributor → FairnessEngine → FeeProofEngine."""

    def _make_distributor_and_participants(self):
        distributor = SubscriptionRevenueDistributor()
        participants = [
            RevenueParticipant("provider_a", service_units=100),
            RevenueParticipant("provider_b", service_units=100),
            RevenueParticipant("provider_c", service_units=100),
        ]
        return distributor, participants

    def test_subscription_flow_distributes_correctly(self) -> None:
        """3 providers with PROFESSIONAL tier: sum of allocations <= gross_revenue."""
        distributor, participants = self._make_distributor_and_participants()
        gross = Decimal("1200.00")
        result = distributor.distribute(gross, participants, tier=SubscriptionTier.PROFESSIONAL)

        total_allocated = sum(result.allocations.values())
        assert total_allocated <= gross, (
            f"Total allocated {total_allocated} exceeds gross revenue {gross}"
        )
        assert len(result.allocations) == 3
        for pid, amount in result.allocations.items():
            assert amount > Decimal("0"), f"Provider {pid} got zero allocation"

    def test_subscription_flow_fairness_passes(self) -> None:
        """3 providers with equal service_units → Gini should be 0 (perfectly fair)."""
        distributor, participants = self._make_distributor_and_participants()
        gross = Decimal("1200.00")
        result = distributor.distribute(gross, participants, tier=SubscriptionTier.PROFESSIONAL)

        fairness_engine = FairnessEngine(FairnessConstraint(max_gini=0.01))
        float_allocs = {pid: float(amt) for pid, amt in result.allocations.items()}
        report = fairness_engine.evaluate(float_allocs)

        assert report.is_fair, (
            f"Expected fair allocation for equal providers; gini={report.gini_coefficient}, "
            f"violations={report.violations}"
        )
        assert abs(report.gini_coefficient) < 0.01, (
            f"Gini should be ~0 for equal providers, got {report.gini_coefficient}"
        )

    def test_subscription_flow_audit_proof_valid(self) -> None:
        """Proof generated from distribution result must verify successfully."""
        distributor, participants = self._make_distributor_and_participants()
        gross = Decimal("1200.00")
        result = distributor.distribute(gross, participants, tier=SubscriptionTier.PROFESSIONAL)

        proof_engine = FeeProofEngine()
        inputs = {
            "tier": SubscriptionTier.PROFESSIONAL.value,
            "gross_revenue": float(gross),
            "participant_count": len(participants),
        }
        proof = proof_engine.generate_proof(
            run_id="subscription-flow-001",
            amount=float(gross),
            currency="USD",
            inputs=inputs,
        )

        assert proof_engine.verify_proof(proof) is True
        assert proof.verify() is True
        assert proof.proof_hash != ""

    def test_subscription_flow_deterministic(self) -> None:
        """Calling distribute twice with same args produces identical allocations."""
        distributor = SubscriptionRevenueDistributor()
        gross = Decimal("1200.00")
        participants_1 = [
            RevenueParticipant("provider_a", service_units=100),
            RevenueParticipant("provider_b", service_units=100),
            RevenueParticipant("provider_c", service_units=100),
        ]
        participants_2 = [
            RevenueParticipant("provider_a", service_units=100),
            RevenueParticipant("provider_b", service_units=100),
            RevenueParticipant("provider_c", service_units=100),
        ]

        result_1 = distributor.distribute(gross, participants_1, tier=SubscriptionTier.PROFESSIONAL)
        result_2 = distributor.distribute(gross, participants_2, tier=SubscriptionTier.PROFESSIONAL)

        assert result_1.allocations == result_2.allocations, (
            f"Non-deterministic: run1={result_1.allocations}, run2={result_2.allocations}"
        )


# ===========================================================================
# Flow 2: License Fee → Split → Distribution → Proof
# ===========================================================================

class TestLicenseFeeDistributionProofFlow:
    """Flow 2: LicenseFeeSplitter → FeeDistributionEngine → FeeProofEngine → FairnessEngine."""

    def test_license_flow_split_conservation(self) -> None:
        """platform + creator + validator + reserve must equal the original amount."""
        splitter = LicenseFeeSplitter()
        amount = Decimal("1000.00")
        result = splitter.split(amount, LicenseType.COMMERCIAL)

        total_split = (
            result.allocations[SplitRecipient.PLATFORM]
            + result.allocations[SplitRecipient.CREATOR]
            + result.allocations[SplitRecipient.VALIDATOR]
            + result.allocations[SplitRecipient.RESERVE]
            + result.residual
        )
        assert abs(total_split - amount) < Decimal("0.001"), (
            f"Split not conserved: expected {amount}, got {total_split}"
        )

    def test_license_flow_validator_share_distributed(self) -> None:
        """Validator portion of license fee further distributed to fee participants, each > 0."""
        splitter = LicenseFeeSplitter()
        amount = Decimal("1000.00")
        split_result = splitter.split(amount, LicenseType.COMMERCIAL)

        validator_share = split_result.allocations[SplitRecipient.VALIDATOR]
        assert validator_share > Decimal("0"), "Validator share must be positive for COMMERCIAL"

        fee_engine = FeeDistributionEngine()
        participants = [
            FeeParticipant("v1", ParticipantRole.VALIDATOR, 0.9),
            FeeParticipant("v2", ParticipantRole.VALIDATOR, 0.8),
            FeeParticipant("v3", ParticipantRole.VALIDATOR, 0.7),
        ]
        dist_result = fee_engine.distribute(validator_share, participants)

        for pid, alloc in dist_result.allocations.items():
            assert alloc > Decimal("0"), f"Validator {pid} received zero allocation"

    def test_license_flow_full_chain_proof_valid(self) -> None:
        """Generate proof from split result inputs, verify returns True."""
        splitter = LicenseFeeSplitter()
        amount = Decimal("1000.00")
        split_result = splitter.split(amount, LicenseType.COMMERCIAL)

        proof_engine = FeeProofEngine()
        inputs = {
            "license_type": LicenseType.COMMERCIAL.value,
            "total_amount": float(amount),
            "platform": float(split_result.allocations[SplitRecipient.PLATFORM]),
            "creator": float(split_result.allocations[SplitRecipient.CREATOR]),
            "validator": float(split_result.allocations[SplitRecipient.VALIDATOR]),
            "reserve": float(split_result.allocations[SplitRecipient.RESERVE]),
        }
        proof = proof_engine.generate_proof(
            run_id="license-flow-001",
            amount=float(amount),
            currency="SSID",
            inputs=inputs,
        )

        assert proof_engine.verify_proof(proof) is True
        assert proof.proof_hash != ""

    def test_license_flow_idempotent(self) -> None:
        """Calling split twice with same args produces identical SplitResult."""
        splitter = LicenseFeeSplitter()
        amount = Decimal("1000.00")

        result_1 = splitter.split(amount, LicenseType.COMMERCIAL)
        result_2 = splitter.split(amount, LicenseType.COMMERCIAL)

        assert result_1.allocations == result_2.allocations, (
            f"Non-idempotent: run1={result_1.allocations}, run2={result_2.allocations}"
        )
        assert result_1.residual == result_2.residual


# ===========================================================================
# Flow 3: Identity Score → Reward → Governance → Fairness
# ===========================================================================

class TestRewardGovernanceFairnessProofFlow:
    """Flow 3: RewardHandler → GovernanceRewardEngine → FairnessEngine → FeeProofEngine."""

    def _make_reward_events(self):
        return [
            RewardEvent("evt-001", "alice", RewardAction.IDENTITY_VERIFICATION, quality_score=0.9, quantity=5),
            RewardEvent("evt-002", "bob", RewardAction.DATA_PROVISION, quality_score=0.8, quantity=3),
            RewardEvent("evt-003", "carol", RewardAction.GOVERNANCE_VOTE, quality_score=1.0, quantity=2),
            RewardEvent("evt-004", "alice", RewardAction.AUDIT_CONTRIBUTION, quality_score=0.95, quantity=1),
            RewardEvent("evt-005", "bob", RewardAction.STAKING, quality_score=0.7, quantity=10),
        ]

    def _make_governance_participants(self):
        return [
            GovernanceParticipant("alice", activities=[
                GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                GovernanceActivity(GovernanceActivityType.PROPOSAL, weight=2.0),
            ]),
            GovernanceParticipant("bob", activities=[
                GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                GovernanceActivity(GovernanceActivityType.REVIEW, weight=1.5),
            ]),
            GovernanceParticipant("carol", activities=[
                GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
            ]),
        ]

    def test_reward_governance_flow_rewards_computed(self) -> None:
        """Batch of identity + governance events: all participants get > 0 rewards."""
        handler = RewardHandler()
        events = self._make_reward_events()
        batch_result = handler.calculate_batch(events)

        assert batch_result.total_rewarded > Decimal("0")
        for pid, total in batch_result.participant_totals.items():
            assert total > Decimal("0"), f"Participant {pid} got zero reward"

        # All event IDs should have allocations
        event_ids = {a.event_id for a in batch_result.allocations}
        assert event_ids == {"evt-001", "evt-002", "evt-003", "evt-004", "evt-005"}

    def test_reward_governance_flow_conservation(self) -> None:
        """Sum of individual rewards equals total_rewarded; governance pool conserved."""
        handler = RewardHandler()
        events = self._make_reward_events()
        batch_result = handler.calculate_batch(events)

        sum_individual = sum(a.final_reward for a in batch_result.allocations)
        assert abs(sum_individual - batch_result.total_rewarded) < Decimal("0.000001"), (
            f"Batch total mismatch: sum={sum_individual}, total={batch_result.total_rewarded}"
        )

        gov_engine = GovernanceRewardEngine()
        participants = self._make_governance_participants()
        pool = Decimal("300.00")
        gov_result = gov_engine.distribute(pool, participants)

        gov_total_out = sum(gov_result.allocations.values()) + gov_result.residual
        assert abs(gov_total_out - pool) < Decimal("0.001"), (
            f"Governance pool not conserved: {gov_total_out} != {pool}"
        )

    def test_reward_governance_flow_fairness_checked(self) -> None:
        """evaluate() returns FairnessReport with is_fair indicator set."""
        handler = RewardHandler()
        events = self._make_reward_events()
        batch_result = handler.calculate_batch(events)

        gov_engine = GovernanceRewardEngine()
        participants = self._make_governance_participants()
        pool = Decimal("300.00")
        gov_result = gov_engine.distribute(pool, participants)

        # Combine reward totals: batch participant_totals + governance allocations
        combined: dict[str, float] = {}
        for pid, amt in batch_result.participant_totals.items():
            combined[pid] = combined.get(pid, 0.0) + float(amt)
        for pid, amt in gov_result.allocations.items():
            combined[pid] = combined.get(pid, 0.0) + float(amt)

        fairness_engine = FairnessEngine(FairnessConstraint(max_gini=0.8))
        report = fairness_engine.evaluate(combined)

        # is_fair must be a bool; gini must be in [0, 1]
        assert isinstance(report.is_fair, bool)
        assert 0.0 <= report.gini_coefficient <= 1.0

    def test_reward_governance_flow_proof_chain(self) -> None:
        """Proof generated from combined rewards must verify successfully."""
        handler = RewardHandler()
        events = self._make_reward_events()
        batch_result = handler.calculate_batch(events)

        gov_engine = GovernanceRewardEngine()
        participants = self._make_governance_participants()
        pool = Decimal("300.00")
        gov_result = gov_engine.distribute(pool, participants)

        total_rewards = float(batch_result.total_rewarded) + float(pool)
        inputs = {
            "batch_total_rewarded": float(batch_result.total_rewarded),
            "governance_pool": float(pool),
            "participant_count": len(batch_result.participant_totals),
            "governance_participant_count": len(gov_result.allocations),
        }

        proof_engine = FeeProofEngine()
        proof = proof_engine.generate_proof(
            run_id="reward-governance-flow-001",
            amount=total_rewards,
            currency="SSID",
            inputs=inputs,
        )

        assert proof_engine.verify_proof(proof) is True
        assert proof.verify() is True

    def test_reward_governance_flow_idempotent(self) -> None:
        """Same batch of events → same total rewards (no side effects from second call)."""
        handler = RewardHandler()

        events_1 = self._make_reward_events()
        events_2 = self._make_reward_events()

        result_1 = handler.calculate_batch(events_1)
        result_2 = handler.calculate_batch(events_2)

        assert result_1.total_rewarded == result_2.total_rewarded, (
            f"Non-idempotent: run1={result_1.total_rewarded}, run2={result_2.total_rewarded}"
        )
        assert result_1.participant_totals == result_2.participant_totals
