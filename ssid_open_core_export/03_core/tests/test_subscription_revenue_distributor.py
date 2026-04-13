#!/usr/bin/env python3
"""Unit tests for subscription_revenue_distributor.py.

Covers ROOT-24-LOCK distribution, settlement periods,
ratio validation, and hash-only evidence.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subscription_revenue_distributor import (
    ROOT_24_NAMES,
    SettlementPeriod,
    SubscriptionRevenueDistributor,
    _default_ratios,
)

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def distributor() -> SubscriptionRevenueDistributor:
    return SubscriptionRevenueDistributor()


# -----------------------------------------------------------------------
# Default ratio tests
# -----------------------------------------------------------------------


class TestDefaultRatios:
    def test_exactly_24_roots(self) -> None:
        ratios = _default_ratios()
        assert len(ratios) == 24

    def test_all_canonical_roots_present(self) -> None:
        ratios = _default_ratios()
        for root in ROOT_24_NAMES:
            assert root in ratios

    def test_ratios_sum_to_one(self) -> None:
        ratios = _default_ratios()
        total = sum(ratios.values())
        assert abs(total - Decimal("1")) < Decimal("0.001")

    def test_core_has_highest_share(self) -> None:
        ratios = _default_ratios()
        assert ratios["03_core"] == Decimal("0.12")

    def test_all_ratios_positive(self) -> None:
        ratios = _default_ratios()
        for root, ratio in ratios.items():
            assert ratio > Decimal("0"), f"{root} has non-positive ratio"


# -----------------------------------------------------------------------
# Settlement calculation
# -----------------------------------------------------------------------


class TestSettlementCalculation:
    def test_monthly_settlement(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("10000"),
            SettlementPeriod.MONTHLY,
            "2026-03",
        )
        assert result.period == SettlementPeriod.MONTHLY
        assert result.period_label == "2026-03"
        assert result.gross_revenue == Decimal("10000")
        assert len(result.allocations) == 24

    def test_quarterly_settlement(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("30000"),
            SettlementPeriod.QUARTERLY,
            "2026-Q1",
        )
        assert result.period == SettlementPeriod.QUARTERLY
        assert result.period_label == "2026-Q1"

    def test_allocations_cover_all_roots(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("10000"),
            SettlementPeriod.MONTHLY,
            "2026-03",
        )
        root_names = [a.root_name for a in result.allocations]
        assert sorted(root_names) == sorted(ROOT_24_NAMES)

    def test_allocations_sum_close_to_gross(self, distributor: SubscriptionRevenueDistributor) -> None:
        gross = Decimal("12345.67")
        result = distributor.calculate_settlement(
            gross,
            SettlementPeriod.MONTHLY,
            "2026-01",
        )
        total_allocated = sum(a.amount for a in result.allocations)
        assert abs(gross - total_allocated - result.remainder) < Decimal("0.01")

    def test_core_gets_largest_share(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("10000"),
            SettlementPeriod.MONTHLY,
            "2026-03",
        )
        core_alloc = next(a for a in result.allocations if a.root_name == "03_core")
        assert core_alloc.amount == Decimal("1200.00")


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_revenue(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("0"),
            SettlementPeriod.MONTHLY,
            "2026-01",
        )
        assert all(a.amount == Decimal("0.00") for a in result.allocations)

    def test_negative_revenue_raises(self, distributor: SubscriptionRevenueDistributor) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            distributor.calculate_settlement(
                Decimal("-100"),
                SettlementPeriod.MONTHLY,
                "2026-01",
            )

    def test_large_revenue(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("100000000"),
            SettlementPeriod.QUARTERLY,
            "2026-Q4",
        )
        assert len(result.allocations) == 24


# -----------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------


class TestRatioValidation:
    def test_missing_root_raises(self) -> None:
        bad_ratios = {root: Decimal("0.04") for root in ROOT_24_NAMES[:23]}
        # Missing 24th root
        with pytest.raises(ValueError, match="Missing ratio"):
            SubscriptionRevenueDistributor(ratios=bad_ratios)

    def test_negative_ratio_raises(self) -> None:
        ratios = _default_ratios()
        ratios["03_core"] = Decimal("-0.05")
        with pytest.raises(ValueError, match="Negative ratio"):
            SubscriptionRevenueDistributor(ratios=ratios)

    def test_ratios_not_summing_to_one_raises(self) -> None:
        ratios = {root: Decimal("0.01") for root in ROOT_24_NAMES}
        # Sum = 0.24, not 1.0
        with pytest.raises(ValueError, match="sum to"):
            SubscriptionRevenueDistributor(ratios=ratios)

    def test_get_ratios_returns_copy(self, distributor: SubscriptionRevenueDistributor) -> None:
        r1 = distributor.get_ratios()
        r2 = distributor.get_ratios()
        assert r1 == r2
        assert r1 is not r2


# -----------------------------------------------------------------------
# Evidence
# -----------------------------------------------------------------------


class TestEvidence:
    def test_evidence_hash_sha256(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("5000"),
            SettlementPeriod.MONTHLY,
            "2026-06",
        )
        assert len(result.evidence_hash) == 64

    def test_settlement_id_present(self, distributor: SubscriptionRevenueDistributor) -> None:
        result = distributor.calculate_settlement(
            Decimal("5000"),
            SettlementPeriod.MONTHLY,
            "2026-06",
        )
        assert len(result.settlement_id) == 16
