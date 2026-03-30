#!/usr/bin/env python3
"""P3.1 Determinism and idempotency tests for all 8 productive core modules.

Verifies that:
- All engines produce identical outputs for identical inputs across N runs
- Independent calls are isolated (no shared mutable state between calls)

SoT v4.1.0 | ROOT-24-LOCK
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_core"))
sys.path.insert(0, str(_REPO_ROOT / "08_identity_score"))

from fee_distribution_engine import (
    FeeDistributionEngine,
)
from subscription_revenue_distributor import (
    SubscriptionRevenueDistributor,
    SettlementPeriod,
)
from license_fee_splitter import (
    LicenseFeeSplitter,
    LicenseType,
    SplitRecipient,
)
from governance_reward_engine import (
    GovernanceActivity,
    GovernanceActivityType,
    GovernanceParticipant,
    GovernanceRewardEngine,
)
from reward_handler import (
    RewardHandler,
    RewardStatus,
    TrustLevel,
    VerificationAction,
)
from fee_proof_engine import AllocationLine, FeeBoundary, FeeProofEngine
from identity_fee_router import (
    IdentityFeeRouter,
    ValidatorProfile,
    VerificationType,
)

_N_RUNS = 5


class TestDeterminism:
    """Verify that all engines produce identical results across 5 runs with identical inputs."""

    def test_fee_distribution_deterministic(self) -> None:
        """5 runs with identical inputs → all allocation tuples identical."""
        engine = FeeDistributionEngine()
        total = Decimal("500.00")

        results = [
            engine.calculate(total).allocations
            for _ in range(_N_RUNS)
        ]

        baseline = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == baseline, (
                f"FeeDistributionEngine: run {i} differs from run 1\n"
                f"run1={baseline}\nrun{i}={result}"
            )

    def test_subscription_deterministic(self) -> None:
        """5 runs of subscription distribution → identical allocations."""
        distributor = SubscriptionRevenueDistributor()
        gross = Decimal("1000.00")

        results = []
        for _ in range(_N_RUNS):
            r = distributor.calculate_settlement(
                gross, SettlementPeriod.MONTHLY, "2026-03"
            )
            results.append(r.allocations)

        baseline = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == baseline, (
                f"SubscriptionRevenueDistributor: run {i} differs from run 1"
            )

    def test_license_split_deterministic(self) -> None:
        """5 runs of license split → identical SplitResult allocations."""
        splitter = LicenseFeeSplitter()
        amount = Decimal("1000.00")

        results = [
            splitter.split(amount, LicenseType.COMMERCIAL).allocations
            for _ in range(_N_RUNS)
        ]

        baseline = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == baseline, (
                f"LicenseFeeSplitter: run {i} differs from run 1"
            )

    def test_governance_rewards_deterministic(self) -> None:
        """5 runs of governance reward distribution → identical allocations."""
        engine = GovernanceRewardEngine()
        pool = Decimal("200.00")

        results = []
        for _ in range(_N_RUNS):
            participants = [
                GovernanceParticipant("p1", activities=[
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                    GovernanceActivity(GovernanceActivityType.PROPOSAL, weight=1.0),
                ]),
                GovernanceParticipant("p2", activities=[
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                ]),
            ]
            r = engine.distribute(pool, participants)
            results.append(r.allocations)

        baseline = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == baseline, (
                f"GovernanceRewardEngine: run {i} differs from run 1"
            )

    def test_reward_handler_deterministic(self) -> None:
        """5 runs with identical inputs → identical final_amount (fresh handler each run)."""
        from datetime import datetime, timezone as tz
        fixed_now = datetime(2026, 3, 17, 12, 0, 0, tzinfo=tz.utc)

        results = [
            RewardHandler().calculate_reward(
                "alice",
                VerificationAction.EMAIL_VERIFY,
                TrustLevel.VERIFIED,
                now=fixed_now,
            ).final_amount
            for _ in range(_N_RUNS)
        ]

        baseline = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == baseline, (
                f"RewardHandler: run {i} final_amount {result} differs from run 1 {baseline}"
            )

    def test_proof_hash_deterministic(self) -> None:
        """5 runs with identical inputs → verify_proof always returns True (self-consistent hash)."""
        engine = FeeProofEngine()
        allocations = [
            AllocationLine(
                recipient_id="platform",
                role="platform_fee",
                boundary=FeeBoundary.PEER,
                amount=Decimal("1000.00"),
                ratio=Decimal("1.0"),
            )
        ]

        for _ in range(_N_RUNS):
            proof = engine.generate_proof(
                Decimal("1000.00"), FeeBoundary.PEER, allocations
            )
            result = engine.verify_proof(proof)
            is_valid = result.hash_valid if hasattr(result, "hash_valid") else bool(result)
            assert is_valid, (
                "FeeProofEngine: verify_proof returned invalid for freshly-generated proof"
            )


class TestIdempotency:
    """Verify that independent calls are isolated and do not accumulate state."""

    def test_fee_distribution_idempotent(self) -> None:
        """Distributing the same fee twice produces two independent results, not cumulative."""
        engine = FeeDistributionEngine()

        result_1 = engine.calculate(Decimal("100.00"))
        result_2 = engine.calculate(Decimal("100.00"))

        # Each call is independent — both should have the same per-stakeholder allocations
        assert result_1.allocations == result_2.allocations, (
            "FeeDistributionEngine: two identical calls produced different allocations"
        )

        # Neither call should return doubled amounts from shared state
        for alloc in result_1.allocations:
            assert alloc.amount <= Decimal("100.00"), (
                f"FeeDistributionEngine: allocation {alloc.stakeholder_id} "
                f"({alloc.amount}) exceeds fee — possible state accumulation"
            )
        for alloc in result_2.allocations:
            assert alloc.amount <= Decimal("100.00")

    def test_identity_router_idempotent(self) -> None:
        """Routing the same fee twice creates 2 separate routing results, not cumulative."""
        router = IdentityFeeRouter()
        validators = [
            ValidatorProfile("val1", supported_types=[VerificationType.EMAIL], reliability_score=0.9),
            ValidatorProfile("val2", supported_types=[VerificationType.EMAIL], reliability_score=0.8),
        ]

        result_1 = router.route_fee(
            VerificationType.EMAIL,
            Decimal("50.00"),
            eligible_validators=validators,
        )
        result_2 = router.route_fee(
            VerificationType.EMAIL,
            Decimal("50.00"),
            eligible_validators=validators,
        )

        # Each routing result should reference exactly 50.00, not 100.00
        total_1 = sum(result_1.validator_allocations.values()) + result_1.platform_fee
        total_2 = sum(result_2.validator_allocations.values()) + result_2.platform_fee

        assert total_1 <= Decimal("50.00") + Decimal("0.01"), (
            f"Router result_1 total {total_1} exceeds single routing amount"
        )
        assert total_2 <= Decimal("50.00") + Decimal("0.01"), (
            f"Router result_2 total {total_2} exceeds single routing amount"
        )

        # Both calls should produce the same per-validator allocations (same inputs)
        assert result_1.validator_allocations == result_2.validator_allocations, (
            "IdentityFeeRouter: two identical calls produced different validator allocations"
        )
