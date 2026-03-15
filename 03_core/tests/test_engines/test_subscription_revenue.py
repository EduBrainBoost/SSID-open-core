"""Tests for SubscriptionRevenueDistributor.

Covers: revenue share calculation, tiered distribution, payout reports,
evidence hashing, edge cases, and determinism.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from subscription_revenue_distributor import (
    SubscriptionRevenueDistributor,
    ValidationError,
)


@pytest.fixture()
def distributor() -> SubscriptionRevenueDistributor:
    return SubscriptionRevenueDistributor()


# ---------------------------------------------------------------------------
# Test 1: Revenue share sums to total revenue
# ---------------------------------------------------------------------------

def test_revenue_share_sums_to_total(distributor: SubscriptionRevenueDistributor) -> None:
    subscription = {"id": "sub-001", "revenue": "1200.00"}
    contributors = {"creator": "60", "platform": "30", "infra": "10"}
    result = distributor.calculate_revenue_share(subscription, contributors)
    total = sum(Decimal(v) for v in result.shares.values())
    assert total == Decimal("1200.00"), f"Expected 1200.00, got {total}"


# ---------------------------------------------------------------------------
# Test 2: Revenue share assigns correct proportions
# ---------------------------------------------------------------------------

def test_revenue_share_correct_proportions(distributor: SubscriptionRevenueDistributor) -> None:
    subscription = {"id": "sub-002", "revenue": "1000"}
    contributors = {"author": "70", "platform": "30"}
    result = distributor.calculate_revenue_share(subscription, contributors)
    assert Decimal(result.shares["platform"]) == Decimal("300")
    assert Decimal(result.shares["author"]) == Decimal("700")


# ---------------------------------------------------------------------------
# Test 3: Revenue share is deterministic
# ---------------------------------------------------------------------------

def test_revenue_share_is_deterministic(distributor: SubscriptionRevenueDistributor) -> None:
    subscription = {"id": "sub-003", "revenue": "777.77"}
    contributors = {"a": "50", "b": "50"}
    r1 = distributor.calculate_revenue_share(subscription, contributors)
    r2 = distributor.calculate_revenue_share(subscription, contributors)
    assert r1.evidence_hash == r2.evidence_hash
    assert r1.shares == r2.shares


# ---------------------------------------------------------------------------
# Test 4: Missing revenue in subscription raises ValidationError
# ---------------------------------------------------------------------------

def test_missing_revenue_raises_error(distributor: SubscriptionRevenueDistributor) -> None:
    with pytest.raises(ValidationError, match="revenue"):
        distributor.calculate_revenue_share({"id": "sub-x"}, {"a": "100"})


# ---------------------------------------------------------------------------
# Test 5: Tiered distribution allocates correctly across tiers
# ---------------------------------------------------------------------------

def test_tiered_distribution_applies_rates(distributor: SubscriptionRevenueDistributor) -> None:
    tiers = [
        {"name": "bronze", "threshold": "500", "rate": "0.05"},
        {"name": "gold", "threshold": None, "rate": "0.10"},
    ]
    result = distributor.apply_tiered_distribution("1000", tiers)
    bronze = Decimal(result.tiers_applied[0].allocated)
    gold = Decimal(result.tiers_applied[1].allocated)
    # bronze tier: 500 * 0.05 = 25
    assert bronze == Decimal("25.00000000")
    # gold tier: 500 * 0.10 = 50
    assert gold == Decimal("50.00000000")


# ---------------------------------------------------------------------------
# Test 6: Tiered distribution evidence hash is 64 chars
# ---------------------------------------------------------------------------

def test_tiered_distribution_evidence_hash(distributor: SubscriptionRevenueDistributor) -> None:
    tiers = [{"name": "flat", "threshold": None, "rate": "0.20"}]
    result = distributor.apply_tiered_distribution("100", tiers)
    assert len(result.evidence_hash) == 64
    assert len(result.input_hash) == 64


# ---------------------------------------------------------------------------
# Test 7: Payout report aggregates multiple distributions
# ---------------------------------------------------------------------------

def test_payout_report_aggregates_distributions(distributor: SubscriptionRevenueDistributor) -> None:
    sub_a = {"id": "sub-A", "revenue": "500"}
    sub_b = {"id": "sub-B", "revenue": "500"}
    contributors = {"creator": "80", "platform": "20"}

    dist_a = distributor.calculate_revenue_share(sub_a, contributors)
    dist_b = distributor.calculate_revenue_share(sub_b, contributors)

    report = distributor.generate_payout_report("2026-Q1", [dist_a, dist_b])
    assert report.distribution_count == 2
    assert Decimal(report.total_distributed) == Decimal("1000")
    assert Decimal(report.per_contributor["creator"]) == Decimal("800")
    assert Decimal(report.per_contributor["platform"]) == Decimal("200")


# ---------------------------------------------------------------------------
# Test 8: Payout report evidence hash is deterministic
# ---------------------------------------------------------------------------

def test_payout_report_is_deterministic(distributor: SubscriptionRevenueDistributor) -> None:
    sub = {"id": "sub-Z", "revenue": "300"}
    dist = distributor.calculate_revenue_share(sub, {"a": "100"})
    r1 = distributor.generate_payout_report("2026-Q2", [dist])
    r2 = distributor.generate_payout_report("2026-Q2", [dist])
    assert r1.evidence_hash == r2.evidence_hash


# ---------------------------------------------------------------------------
# Test 9: Empty contributors raises ValidationError
# ---------------------------------------------------------------------------

def test_empty_contributors_raises_error(distributor: SubscriptionRevenueDistributor) -> None:
    with pytest.raises(ValidationError, match="empty"):
        distributor.calculate_revenue_share({"id": "sub-1", "revenue": "100"}, {})


# ---------------------------------------------------------------------------
# Test 10: Subscription id is preserved in result
# ---------------------------------------------------------------------------

def test_subscription_id_preserved_in_result(distributor: SubscriptionRevenueDistributor) -> None:
    subscription = {"id": "my-unique-sub-id", "revenue": "50"}
    result = distributor.calculate_revenue_share(subscription, {"contributor": "100"})
    assert result.subscription_id == "my-unique-sub-id"
