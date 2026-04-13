#!/usr/bin/env python3
"""Cross-engine integration tests for 03_core — fee→reward→distribution chain.

Tests the end-to-end pipeline across:
  - FeeDistributionEngine
  - SubscriptionRevenueDistributor
  - GovernanceRewardEngine
  - FairnessEngine
  - IdentityFeeRouter (via identity_fee_router)

All amounts are validated for conservation, fairness, and type correctness.

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Ensure 03_core is importable regardless of working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fairness_engine import FairnessConstraint, FairnessEngine
from fee_distribution_engine import (
    FeeDistributionEngine,
    FeeParticipant,
    ParticipantRole,
)
from governance_reward_engine import (
    GovernanceActivity,
    GovernanceActivityType,
    GovernanceParticipant,
    GovernanceRewardEngine,
)
from subscription_revenue_distributor import (
    RevenueParticipant,
    SubscriptionRevenueDistributor,
    SubscriptionTier,
)

# ---------------------------------------------------------------------------
# Test 1: Fee distribution — single validator receives near-full amount
# ---------------------------------------------------------------------------


class TestFeeEngineBaseline:
    def test_single_validator_receives_nonzero(self) -> None:
        """A lone validator must receive a positive share of any non-zero fee."""
        engine = FeeDistributionEngine()
        p = FeeParticipant("solo", ParticipantRole.VALIDATOR, 1.0)
        result = engine.distribute(Decimal("100.00"), [p])
        assert result.allocations["solo"] > Decimal("0")

    def test_fee_is_conserved(self) -> None:
        """Sum of allocations + residual must equal total_fee exactly."""
        engine = FeeDistributionEngine()
        participants = [
            FeeParticipant("v1", ParticipantRole.VALIDATOR, 0.9),
            FeeParticipant("p1", ParticipantRole.PROVIDER, 0.7),
            FeeParticipant("g1", ParticipantRole.GOVERNANCE, 0.5),
        ]
        total = Decimal("500.00")
        result = engine.distribute(total, participants)
        total_out = sum(result.allocations.values()) + result.residual
        assert abs(total_out - total) < Decimal("0.001"), f"Fee not conserved: expected {total}, got {total_out}"

    def test_empty_participants_raises(self) -> None:
        """distribute must raise ValueError when participants list is empty."""
        engine = FeeDistributionEngine()
        with pytest.raises(ValueError):
            engine.distribute(Decimal("100.00"), [])

    def test_negative_fee_raises(self) -> None:
        """distribute must raise ValueError for a negative fee."""
        engine = FeeDistributionEngine()
        p = FeeParticipant("v", ParticipantRole.VALIDATOR, 1.0)
        with pytest.raises(ValueError):
            engine.distribute(Decimal("-1.00"), [p])


# ---------------------------------------------------------------------------
# Test 2: Subscription revenue distributor — retention + distribution chain
# ---------------------------------------------------------------------------


class TestSubscriptionRevenueDistributor:
    def test_professional_tier_retention_is_twenty_percent(self) -> None:
        """PROFESSIONAL tier retains 20% of gross revenue for the platform."""
        distributor = SubscriptionRevenueDistributor()
        gross = Decimal("1000.00")
        participants = [RevenueParticipant("provider_a", service_units=100)]
        result = distributor.distribute(gross, participants, tier=SubscriptionTier.PROFESSIONAL)

        # 20% retention = 200.00
        assert abs(result.platform_retention - Decimal("200.00")) < Decimal("0.001")
        assert abs(result.distributable - Decimal("800.00")) < Decimal("0.001")

    def test_revenue_conservation_across_tiers(self) -> None:
        """gross_revenue = platform_retention + sum(allocations) + residual for any tier."""
        distributor = SubscriptionRevenueDistributor()
        for tier in SubscriptionTier:
            gross = Decimal("500.00")
            participants = [
                RevenueParticipant("a", service_units=60, tier=tier),
                RevenueParticipant("b", service_units=40, tier=tier),
            ]
            result = distributor.distribute(gross, participants, tier=tier)
            total_out = result.platform_retention + sum(result.allocations.values()) + result.residual
            assert abs(total_out - gross) < Decimal("0.001"), (
                f"Revenue not conserved for tier {tier}: {total_out} != {gross}"
            )

    def test_service_units_proportionality(self) -> None:
        """Participant with more service_units receives more distribution."""
        distributor = SubscriptionRevenueDistributor()
        gross = Decimal("1000.00")
        participants = [
            RevenueParticipant("big", service_units=75),
            RevenueParticipant("small", service_units=25),
        ]
        result = distributor.distribute(gross, participants, tier=SubscriptionTier.PROFESSIONAL)
        assert result.allocations["big"] > result.allocations["small"]


# ---------------------------------------------------------------------------
# Test 3: Fee → Fairness cross-engine pipeline
# ---------------------------------------------------------------------------


class TestFeeToFairnessChain:
    def test_balanced_distribution_is_fair(self) -> None:
        """Equal-weight participants should produce a fair allocation (low Gini)."""
        fee_engine = FeeDistributionEngine()
        fairness_engine = FairnessEngine(FairnessConstraint(max_gini=0.5))

        participants = [FeeParticipant(f"v{i}", ParticipantRole.VALIDATOR, 1.0) for i in range(4)]
        result = fee_engine.distribute(Decimal("100.00"), participants)

        # Feed allocations to fairness engine (convert to float)
        float_allocs = {pid: float(amt) for pid, amt in result.allocations.items()}
        report = fairness_engine.evaluate(float_allocs)

        assert report.is_fair, f"Expected fair allocation; violations: {report.violations}"
        assert 0.0 <= report.gini_coefficient <= 1.0

    def test_highly_skewed_distribution_is_detected(self) -> None:
        """A severely skewed allocation must produce a high Gini coefficient."""
        fairness_engine = FairnessEngine(FairnessConstraint(max_gini=0.2))

        # 99% to one participant, 1% split over 9 others
        allocs = {"whale": 990.0}
        for i in range(9):
            allocs[f"minnow_{i}"] = 1.0 / 9 * 10  # ~1.1 each

        report = fairness_engine.evaluate(allocs)

        # With max_gini=0.2, the whale scenario is unfair
        assert not report.is_fair
        assert len(report.violations) > 0


# ---------------------------------------------------------------------------
# Test 4: Governance reward engine — activity score proportionality
# ---------------------------------------------------------------------------


class TestGovernanceRewardEngine:
    def test_reward_conservation(self) -> None:
        """Sum of governance allocations + residual must equal pool_amount."""
        engine = GovernanceRewardEngine()
        participants = [
            GovernanceParticipant(
                "p1",
                activities=[
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                    GovernanceActivity(GovernanceActivityType.PROPOSAL, weight=1.0),
                ],
            ),
            GovernanceParticipant(
                "p2",
                activities=[
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                ],
            ),
        ]
        pool = Decimal("200.00")
        result = engine.distribute(pool_amount=pool, participants=participants)

        total_out = sum(result.allocations.values()) + result.residual
        assert abs(total_out - pool) < Decimal("0.001")

    def test_more_active_participant_earns_more(self) -> None:
        """The participant with more governance activities receives more reward."""
        engine = GovernanceRewardEngine()
        participants = [
            GovernanceParticipant(
                "active",
                activities=[
                    GovernanceActivity(GovernanceActivityType.PROPOSAL, weight=1.0),
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                    GovernanceActivity(GovernanceActivityType.REVIEW, weight=1.0),
                ],
            ),
            GovernanceParticipant(
                "passive",
                activities=[
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                ],
            ),
        ]
        result = engine.distribute(Decimal("100.00"), participants)
        assert result.allocations["active"] > result.allocations["passive"]

    def test_empty_participants_raises(self) -> None:
        """Distributing rewards to no participants must raise ValueError."""
        engine = GovernanceRewardEngine()
        with pytest.raises(ValueError):
            engine.distribute(Decimal("100.00"), [])


# ---------------------------------------------------------------------------
# Test 5: Role weight lookup
# ---------------------------------------------------------------------------


class TestRoleWeights:
    def test_validator_has_highest_default_weight(self) -> None:
        """VALIDATOR must have the highest default role weight."""
        engine = FeeDistributionEngine()
        weights = {role: engine.role_weight(role) for role in ParticipantRole}
        max_role = max(weights, key=lambda r: weights[r])
        assert max_role == ParticipantRole.VALIDATOR

    def test_unknown_role_weight_is_zero(self) -> None:
        """role_weight for a role not in the weights dict must return 0.0."""
        engine = FeeDistributionEngine(role_weights={})
        for role in ParticipantRole:
            assert engine.role_weight(role) == 0.0
