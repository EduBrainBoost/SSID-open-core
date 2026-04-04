"""Tests for identity_fee_router."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from identity_fee_router import (
    DEFAULT_FEE_SCHEDULE,
    FeeScheduleEntry,
    IdentityFeeRouter,
    ValidatorProfile,
    VerificationType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _email_validator(vid: str, score: float = 1.0) -> ValidatorProfile:
    return ValidatorProfile(vid, [VerificationType.EMAIL], reliability_score=score)


def _gov_id_validator(vid: str, score: float = 1.0) -> ValidatorProfile:
    return ValidatorProfile(vid, [VerificationType.GOVERNMENT_ID], reliability_score=score)


def _multi_validator(vid: str, score: float = 1.0) -> ValidatorProfile:
    return ValidatorProfile(
        vid,
        [VerificationType.EMAIL, VerificationType.PHONE],
        reliability_score=score,
    )


# ---------------------------------------------------------------------------
# ValidatorProfile validation
# ---------------------------------------------------------------------------


class TestValidatorProfile:
    def test_valid_profile(self) -> None:
        v = _email_validator("v1", score=0.8)
        assert v.reliability_score == 0.8

    def test_reliability_score_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="reliability_score"):
            ValidatorProfile("v1", [VerificationType.EMAIL], reliability_score=1.5)

    def test_reliability_score_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            ValidatorProfile("v1", [VerificationType.EMAIL], reliability_score=-0.1)

    def test_empty_supported_types_raises(self) -> None:
        with pytest.raises(ValueError, match="supported_types"):
            ValidatorProfile("v1", [])


# ---------------------------------------------------------------------------
# FeeScheduleEntry validation
# ---------------------------------------------------------------------------


class TestFeeScheduleEntry:
    def test_valid_entry(self) -> None:
        entry = FeeScheduleEntry(VerificationType.EMAIL, Decimal("1.00"), 0.10)
        assert entry.base_fee == Decimal("1.00")

    def test_negative_base_fee_raises(self) -> None:
        with pytest.raises(ValueError, match="base_fee"):
            FeeScheduleEntry(VerificationType.EMAIL, Decimal("-1.00"))

    def test_platform_cut_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="platform_cut"):
            FeeScheduleEntry(VerificationType.EMAIL, Decimal("1.00"), platform_cut=1.5)


# ---------------------------------------------------------------------------
# route_fee — basic routing
# ---------------------------------------------------------------------------


class TestRouteFee:
    def setup_method(self) -> None:
        self.router = IdentityFeeRouter()

    def test_single_validator_receives_validator_pool(self) -> None:
        v = _email_validator("v1")
        result = self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [v])
        assert "v1" in result.validator_allocations
        assert result.validator_allocations["v1"] > Decimal("0")

    def test_platform_fee_plus_validator_pool_equals_total(self) -> None:
        validators = [_email_validator("v1"), _email_validator("v2", 0.5)]
        result = self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), validators)
        total = result.platform_fee + sum(result.validator_allocations.values()) + result.residual
        assert abs(total - Decimal("1.00")) < Decimal("0.001")

    def test_higher_reliability_gets_larger_share(self) -> None:
        validators = [
            _email_validator("high", score=0.9),
            _email_validator("low", score=0.3),
        ]
        result = self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), validators)
        assert result.validator_allocations["high"] > result.validator_allocations["low"]

    def test_no_eligible_validators_full_platform_fee(self) -> None:
        # Phone validator provided, but we route EMAIL
        phone_v = ValidatorProfile("v1", [VerificationType.PHONE])
        result = self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [phone_v])
        assert result.validator_allocations == {}
        assert result.platform_fee == Decimal("1.00")

    def test_no_validators_full_platform_fee(self) -> None:
        result = self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [])
        assert result.platform_fee == Decimal("1.00")
        assert result.validator_allocations == {}

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            self.router.route_fee(VerificationType.EMAIL, Decimal("-1.00"))

    def test_zero_amount_uses_schedule_base_fee(self) -> None:
        v = _email_validator("v1")
        result = self.router.route_fee(VerificationType.EMAIL, Decimal("0"), [v])
        schedule_base = DEFAULT_FEE_SCHEDULE[VerificationType.EMAIL].base_fee
        assert result.total_fee == schedule_base

    def test_government_id_higher_platform_cut(self) -> None:
        email_result = self.router.route_fee(VerificationType.EMAIL, Decimal("10.00"), [_email_validator("ve")])
        gov_result = self.router.route_fee(VerificationType.GOVERNMENT_ID, Decimal("10.00"), [_gov_id_validator("vg")])
        # Government ID has a higher platform_cut rate
        gov_platform_rate = DEFAULT_FEE_SCHEDULE[VerificationType.GOVERNMENT_ID].platform_cut
        email_platform_rate = DEFAULT_FEE_SCHEDULE[VerificationType.EMAIL].platform_cut
        assert gov_platform_rate > email_platform_rate
        assert gov_result.platform_fee > email_result.platform_fee


# ---------------------------------------------------------------------------
# get_validator_earnings
# ---------------------------------------------------------------------------


class TestValidatorEarnings:
    def setup_method(self) -> None:
        self.router = IdentityFeeRouter()

    def test_earnings_accumulate_across_routes(self) -> None:
        v = _email_validator("v1")
        for _ in range(3):
            self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [v])
        earnings = self.router.get_validator_earnings("v1")
        assert earnings > Decimal("0")

    def test_unknown_validator_earnings_zero(self) -> None:
        assert self.router.get_validator_earnings("nonexistent") == Decimal("0")

    def test_two_validators_earnings_independent(self) -> None:
        v1 = _email_validator("v1", score=0.8)
        v2 = _email_validator("v2", score=0.2)
        self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [v1, v2])
        e1 = self.router.get_validator_earnings("v1")
        e2 = self.router.get_validator_earnings("v2")
        assert e1 > e2

    def test_get_all_validator_earnings(self) -> None:
        v1 = _email_validator("v1")
        v2 = _email_validator("v2")
        self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [v1, v2])
        all_earnings = self.router.get_all_validator_earnings()
        assert "v1" in all_earnings
        assert "v2" in all_earnings


# ---------------------------------------------------------------------------
# get_fee_schedule & update_fee_schedule
# ---------------------------------------------------------------------------


class TestFeeSchedule:
    def setup_method(self) -> None:
        self.router = IdentityFeeRouter()

    def test_default_schedule_has_all_types(self) -> None:
        schedule = self.router.get_fee_schedule()
        for vt in VerificationType:
            assert vt in schedule, f"Missing schedule entry for {vt}"

    def test_update_fee_schedule_affects_routing(self) -> None:
        new_entry = FeeScheduleEntry(VerificationType.EMAIL, Decimal("5.00"), platform_cut=0.50)
        self.router.update_fee_schedule(VerificationType.EMAIL, new_entry)
        schedule = self.router.get_fee_schedule()
        assert schedule[VerificationType.EMAIL].base_fee == Decimal("5.00")
        assert schedule[VerificationType.EMAIL].platform_cut == 0.50

    def test_get_fee_schedule_returns_copy(self) -> None:
        schedule1 = self.router.get_fee_schedule()
        schedule1[VerificationType.EMAIL] = FeeScheduleEntry(VerificationType.EMAIL, Decimal("999.00"))
        schedule2 = self.router.get_fee_schedule()
        # Mutation of returned dict must not affect internal schedule
        assert schedule2[VerificationType.EMAIL].base_fee != Decimal("999.00")


# ---------------------------------------------------------------------------
# routing_history
# ---------------------------------------------------------------------------


class TestRoutingHistory:
    def setup_method(self) -> None:
        self.router = IdentityFeeRouter()

    def test_history_grows_with_each_route(self) -> None:
        v = _email_validator("v1")
        for _i in range(4):
            self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [v])
        history = self.router.get_routing_history()
        assert len(history) == 4

    def test_history_returns_copy(self) -> None:
        v = _email_validator("v1")
        self.router.route_fee(VerificationType.EMAIL, Decimal("1.00"), [v])
        history = self.router.get_routing_history()
        history.clear()
        # Internal history must be unaffected
        assert len(self.router.get_routing_history()) == 1
