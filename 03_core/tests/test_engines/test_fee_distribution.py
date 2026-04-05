"""Tests for FeeDistributionEngine.

Covers: percentage distribution, fixed distribution, validation,
apply_distribution evidence hashing, edge cases, and determinism.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fee_distribution_engine import (
    DistributionMode,
    FeeDistributionEngine,
    ValidationError,
)


@pytest.fixture()
def engine() -> FeeDistributionEngine:
    return FeeDistributionEngine()


# ---------------------------------------------------------------------------
# Test 1: Equal percentage distribution sums to total
# ---------------------------------------------------------------------------

def test_percentage_distribution_sums_to_total(engine: FeeDistributionEngine) -> None:
    participants = ["alice", "bob", "carol"]
    weights = {"alice": "33.333334", "bob": "33.333333", "carol": "33.333333"}
    result = engine.calculate_distribution(
        total_amount="100.00",
        participants=participants,
        weights=weights,
        mode=DistributionMode.PERCENTAGE,
    )
    total = sum(Decimal(v) for v in result.values())
    assert total == Decimal("100.00"), f"Expected 100.00, got {total}"


# ---------------------------------------------------------------------------
# Test 2: Unequal percentage distribution assigns correct proportions
# ---------------------------------------------------------------------------

def test_percentage_distribution_correct_proportions(engine: FeeDistributionEngine) -> None:
    participants = ["platform", "creator"]
    weights = {"platform": "30", "creator": "70"}
    result = engine.calculate_distribution(
        total_amount="1000",
        participants=participants,
        weights=weights,
        mode=DistributionMode.PERCENTAGE,
    )
    platform_amount = Decimal(result["platform"])
    creator_amount = Decimal(result["creator"])
    assert platform_amount == Decimal("300"), f"Platform got {platform_amount}"
    assert creator_amount == Decimal("700"), f"Creator got {creator_amount}"


# ---------------------------------------------------------------------------
# Test 3: Fixed distribution allocates exact amounts
# ---------------------------------------------------------------------------

def test_fixed_distribution_allocates_exact_amounts(engine: FeeDistributionEngine) -> None:
    participants = ["ops", "dev", "qa"]
    weights = {"ops": "50.0", "dev": "30.0", "qa": "15.0"}
    result = engine.calculate_distribution(
        total_amount="200.0",
        participants=participants,
        weights=weights,
        mode=DistributionMode.FIXED,
    )
    assert Decimal(result["ops"]) == Decimal("50.0")
    assert Decimal(result["dev"]) == Decimal("30.0")
    assert Decimal(result["qa"]) == Decimal("15.0")


# ---------------------------------------------------------------------------
# Test 4: validate_distribution rejects negative amounts
# ---------------------------------------------------------------------------

def test_validate_distribution_rejects_negative_amounts(engine: FeeDistributionEngine) -> None:
    with pytest.raises(ValidationError, match="negative amount"):
        engine.validate_distribution({"alice": "10.0", "bob": "-5.0"})


# ---------------------------------------------------------------------------
# Test 5: apply_distribution returns DistributionResult with evidence hashes
# ---------------------------------------------------------------------------

def test_apply_distribution_returns_evidence_hashes(engine: FeeDistributionEngine) -> None:
    result = engine.apply_distribution(
        total_amount="500",
        participants=["x", "y"],
        weights={"x": "60", "y": "40"},
        mode=DistributionMode.PERCENTAGE,
    )
    assert len(result.evidence_hash) == 64, "evidence_hash must be 64-char SHA-256 hex"
    assert len(result.input_hash) == 64, "input_hash must be 64-char SHA-256 hex"
    assert result.evidence_hash != result.input_hash


# ---------------------------------------------------------------------------
# Test 6: apply_distribution is deterministic
# ---------------------------------------------------------------------------

def test_apply_distribution_is_deterministic(engine: FeeDistributionEngine) -> None:
    kwargs = dict(
        total_amount="999.99",
        participants=["a", "b", "c"],
        weights={"a": "50", "b": "30", "c": "20"},
        mode=DistributionMode.PERCENTAGE,
    )
    r1 = engine.apply_distribution(**kwargs)
    r2 = engine.apply_distribution(**kwargs)
    assert r1.evidence_hash == r2.evidence_hash
    assert r1.distribution == r2.distribution


# ---------------------------------------------------------------------------
# Test 7: Missing weights for participant raises ValidationError
# ---------------------------------------------------------------------------

def test_missing_weight_raises_error(engine: FeeDistributionEngine) -> None:
    with pytest.raises(ValidationError, match="weights missing"):
        engine.calculate_distribution(
            total_amount="100",
            participants=["alice", "bob"],
            weights={"alice": "100"},
        )


# ---------------------------------------------------------------------------
# Test 8: Fixed weights exceeding total raises ValidationError
# ---------------------------------------------------------------------------

def test_fixed_weights_exceeding_total_raises_error(engine: FeeDistributionEngine) -> None:
    with pytest.raises(ValidationError, match="exceeds total_amount"):
        engine.calculate_distribution(
            total_amount="100",
            participants=["a", "b"],
            weights={"a": "80", "b": "40"},
            mode=DistributionMode.FIXED,
        )


# ---------------------------------------------------------------------------
# Test 9: Zero total_amount raises ValidationError
# ---------------------------------------------------------------------------

def test_zero_total_raises_error(engine: FeeDistributionEngine) -> None:
    with pytest.raises(ValidationError, match="positive"):
        engine.calculate_distribution(
            total_amount="0",
            participants=["a"],
            weights={"a": "100"},
        )


# ---------------------------------------------------------------------------
# Test 10: Last participant absorbs rounding remainder
# ---------------------------------------------------------------------------

def test_last_participant_absorbs_remainder(engine: FeeDistributionEngine) -> None:
    """With an indivisible total the last participant absorbs the remainder."""
    result = engine.apply_distribution(
        total_amount="1",
        participants=["p1", "p2", "p3"],
        weights={"p1": "33.333334", "p2": "33.333333", "p3": "33.333333"},
        mode=DistributionMode.PERCENTAGE,
    )
    total = sum(Decimal(v) for v in result.distribution.values())
    assert total == Decimal("1"), f"Distribution must sum to 1, got {total}"
