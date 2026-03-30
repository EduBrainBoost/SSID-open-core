#!/usr/bin/env python3
"""Unit tests for fee_distribution_engine.py.

Covers tiered distribution, edge cases, evidence hashing,
and non-custodial invariants.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Ensure the module is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fee_distribution_engine import (
    DEFAULT_TIERS,
    DistributionResult,
    FeeAllocation,
    FeeDistributionEngine,
    StakeholderRole,
    TierRule,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def engine() -> FeeDistributionEngine:
    """Engine with default tiers."""
    return FeeDistributionEngine()


@pytest.fixture
def custom_engine() -> FeeDistributionEngine:
    """Engine with a single flat tier for predictable assertions."""
    tier = TierRule(
        name="flat",
        threshold_min=Decimal("0"),
        threshold_max=None,
        splits={
            StakeholderRole.PLATFORM: Decimal("0.50"),
            StakeholderRole.OPERATOR: Decimal("0.30"),
            StakeholderRole.CREATOR: Decimal("0.15"),
            StakeholderRole.RESERVE: Decimal("0.05"),
        },
    )
    return FeeDistributionEngine(tiers=[tier])


# -----------------------------------------------------------------------
# Basic distribution tests
# -----------------------------------------------------------------------

class TestBasicDistribution:
    def test_micro_tier_selected(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("50"))
        assert result.gross_amount == Decimal("50")
        tier_names = {a.tier_name for a in result.allocations}
        assert tier_names == {"micro"}

    def test_standard_tier_selected(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("500"))
        tier_names = {a.tier_name for a in result.allocations}
        assert tier_names == {"standard"}

    def test_enterprise_tier_selected(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("50000"))
        tier_names = {a.tier_name for a in result.allocations}
        assert tier_names == {"enterprise"}

    def test_boundary_100_is_standard(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("100"))
        tier_names = {a.tier_name for a in result.allocations}
        assert tier_names == {"standard"}

    def test_all_roles_present(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("1000"))
        roles = {a.role for a in result.allocations}
        assert roles == {
            StakeholderRole.PLATFORM,
            StakeholderRole.OPERATOR,
            StakeholderRole.CREATOR,
            StakeholderRole.RESERVE,
        }

    def test_allocations_sum_close_to_gross(
        self, engine: FeeDistributionEngine
    ) -> None:
        result = engine.calculate(Decimal("999.99"))
        total_allocated = sum(a.amount for a in result.allocations)
        assert abs(result.gross_amount - total_allocated - result.remainder) < Decimal("0.01")


# -----------------------------------------------------------------------
# Custom / flat tier tests
# -----------------------------------------------------------------------

class TestCustomTier:
    def test_flat_split_100(self, custom_engine: FeeDistributionEngine) -> None:
        result = custom_engine.calculate(Decimal("100"))
        amounts = {a.role: a.amount for a in result.allocations}
        assert amounts[StakeholderRole.PLATFORM] == Decimal("50.00")
        assert amounts[StakeholderRole.OPERATOR] == Decimal("30.00")
        assert amounts[StakeholderRole.CREATOR] == Decimal("15.00")
        assert amounts[StakeholderRole.RESERVE] == Decimal("5.00")

    def test_flat_split_odd_amount(
        self, custom_engine: FeeDistributionEngine
    ) -> None:
        result = custom_engine.calculate(Decimal("33.33"))
        total_allocated = sum(a.amount for a in result.allocations)
        # Total allocated + remainder must equal gross
        assert total_allocated + result.remainder == Decimal("33.33")


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_amount(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("0"))
        assert all(a.amount == Decimal("0.00") for a in result.allocations)

    def test_negative_amount_raises(self, engine: FeeDistributionEngine) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            engine.calculate(Decimal("-1"))

    def test_very_large_amount(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("999999999.99"))
        assert result.gross_amount == Decimal("999999999.99")
        total = sum(a.amount for a in result.allocations)
        assert abs(result.gross_amount - total - result.remainder) < Decimal("0.10")


# -----------------------------------------------------------------------
# Evidence / hash tests
# -----------------------------------------------------------------------

class TestEvidence:
    def test_evidence_hash_is_sha256(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("100"))
        assert len(result.evidence_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.evidence_hash)

    def test_distribution_id_present(self, engine: FeeDistributionEngine) -> None:
        result = engine.calculate(Decimal("100"))
        assert len(result.distribution_id) == 16

    def test_no_pii_in_result(self, engine: FeeDistributionEngine) -> None:
        """Verify no raw PII fields exist in the result."""
        result = engine.calculate(Decimal("100"))
        # stakeholder_ids are opaque strings, not email/phone
        for alloc in result.allocations:
            assert "@" not in alloc.stakeholder_id
            assert "+" not in alloc.stakeholder_id


# -----------------------------------------------------------------------
# TierRule validation
# -----------------------------------------------------------------------

class TestTierRule:
    def test_splits_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="sum to 1"):
            TierRule(
                name="bad",
                threshold_min=Decimal("0"),
                threshold_max=None,
                splits={StakeholderRole.PLATFORM: Decimal("0.50")},
            )

    def test_negative_ratio_rejected(self) -> None:
        with pytest.raises(ValueError, match="negative ratio"):
            TierRule(
                name="bad",
                threshold_min=Decimal("0"),
                threshold_max=None,
                splits={
                    StakeholderRole.PLATFORM: Decimal("1.50"),
                    StakeholderRole.OPERATOR: Decimal("-0.50"),
                },
            )

    def test_list_tiers(self, engine: FeeDistributionEngine) -> None:
        tiers = engine.list_tiers()
        assert len(tiers) == 3
        names = [t.name for t in tiers]
        assert "micro" in names
        assert "standard" in names
        assert "enterprise" in names
