"""Tests for license_fee_splitter."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from license_fee_splitter import (
    LicenseFeeSplitter,
    LicenseType,
    SplitRatios,
    SplitRecipient,
)

# ---------------------------------------------------------------------------
# SplitRatios validation
# ---------------------------------------------------------------------------


class TestSplitRatios:
    def test_valid_ratios(self) -> None:
        r = SplitRatios(platform=0.40, creator=0.40, validator=0.15, reserve=0.05)
        assert abs(r.platform + r.creator + r.validator + r.reserve - 1.0) < 1e-9

    def test_ratios_not_summing_to_one_raises(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            SplitRatios(platform=0.40, creator=0.40, validator=0.10, reserve=0.05)

    def test_negative_ratio_raises(self) -> None:
        with pytest.raises(ValueError):
            SplitRatios(platform=-0.10, creator=0.60, validator=0.30, reserve=0.20)

    def test_ratio_above_one_raises(self) -> None:
        with pytest.raises(ValueError):
            SplitRatios(platform=1.10, creator=0.0, validator=0.0, reserve=-0.10)

    def test_as_dict_keys(self) -> None:
        r = SplitRatios(platform=0.50, creator=0.35, validator=0.10, reserve=0.05)
        d = r.as_dict()
        assert set(d.keys()) == {
            SplitRecipient.PLATFORM,
            SplitRecipient.CREATOR,
            SplitRecipient.VALIDATOR,
            SplitRecipient.RESERVE,
        }


# ---------------------------------------------------------------------------
# LicenseFeeSplitter.split
# ---------------------------------------------------------------------------


class TestLicenseFeeSplitterSplit:
    def setup_method(self) -> None:
        self.splitter = LicenseFeeSplitter()

    def test_split_basic_license(self) -> None:
        result = self.splitter.split(Decimal("100.00"), LicenseType.BASIC)
        assert result.license_type == LicenseType.BASIC
        assert result.total_amount == Decimal("100.00")

    def test_allocations_sum_to_total(self) -> None:
        for lt in LicenseType:
            result = self.splitter.split(Decimal("200.00"), lt)
            total = sum(result.allocations.values()) + result.residual
            assert abs(total - Decimal("200.00")) < Decimal("0.001"), f"Conservation failed for {lt}"

    def test_all_recipients_present(self) -> None:
        result = self.splitter.split(Decimal("100.00"), LicenseType.COMMERCIAL)
        assert SplitRecipient.PLATFORM in result.allocations
        assert SplitRecipient.CREATOR in result.allocations
        assert SplitRecipient.VALIDATOR in result.allocations
        assert SplitRecipient.RESERVE in result.allocations

    def test_zero_amount_distributes_zero(self) -> None:
        result = self.splitter.split(Decimal("0"), LicenseType.STANDARD)
        for alloc in result.allocations.values():
            assert alloc == Decimal("0")

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            self.splitter.split(Decimal("-50"), LicenseType.BASIC)

    def test_commercial_creator_share_larger_than_basic(self) -> None:
        basic_result = self.splitter.split(Decimal("100.00"), LicenseType.BASIC)
        commercial_result = self.splitter.split(Decimal("100.00"), LicenseType.COMMERCIAL)
        assert commercial_result.allocations[SplitRecipient.CREATOR] > basic_result.allocations[SplitRecipient.CREATOR]

    def test_ratios_used_in_result(self) -> None:
        result = self.splitter.split(Decimal("100"), LicenseType.ENTERPRISE)
        assert result.ratios_used is not None

    def test_result_recorded_in_ledger(self) -> None:
        self.splitter.split(Decimal("50.00"), LicenseType.RESEARCH)
        report = self.splitter.get_distribution_report()
        research_entries = [e for e in report if e.license_type == LicenseType.RESEARCH]
        assert len(research_entries) == 1
        assert research_entries[0].split_count == 1


# ---------------------------------------------------------------------------
# configure_ratios
# ---------------------------------------------------------------------------


class TestConfigureRatios:
    def setup_method(self) -> None:
        self.splitter = LicenseFeeSplitter()

    def test_configure_changes_allocation(self) -> None:
        new_ratios = SplitRatios(platform=0.10, creator=0.70, validator=0.15, reserve=0.05)
        self.splitter.configure_ratios(LicenseType.BASIC, new_ratios)
        result = self.splitter.split(Decimal("100.00"), LicenseType.BASIC)
        # creator should now get 70
        assert abs(float(result.allocations[SplitRecipient.CREATOR]) - 70.0) < 0.01

    def test_get_ratios_returns_configured(self) -> None:
        new_ratios = SplitRatios(platform=0.25, creator=0.50, validator=0.20, reserve=0.05)
        self.splitter.configure_ratios(LicenseType.STANDARD, new_ratios)
        retrieved = self.splitter.get_ratios(LicenseType.STANDARD)
        assert retrieved == new_ratios

    def test_get_ratios_none_for_unknown_not_applicable(self) -> None:
        # All default license types should have ratios
        for lt in LicenseType:
            assert self.splitter.get_ratios(lt) is not None


# ---------------------------------------------------------------------------
# get_distribution_report
# ---------------------------------------------------------------------------


class TestGetDistributionReport:
    def setup_method(self) -> None:
        self.splitter = LicenseFeeSplitter()

    def test_empty_report_when_no_splits(self) -> None:
        report = self.splitter.get_distribution_report()
        assert report == []

    def test_report_aggregates_multiple_splits(self) -> None:
        for _ in range(3):
            self.splitter.split(Decimal("100.00"), LicenseType.COMMERCIAL)
        report = self.splitter.get_distribution_report()
        commercial = next(e for e in report if e.license_type == LicenseType.COMMERCIAL)
        assert commercial.split_count == 3
        assert commercial.total_collected == Decimal("300.00")

    def test_report_includes_all_used_types(self) -> None:
        self.splitter.split(Decimal("10"), LicenseType.BASIC)
        self.splitter.split(Decimal("20"), LicenseType.ENTERPRISE)
        report = self.splitter.get_distribution_report()
        types_in_report = {e.license_type for e in report}
        assert LicenseType.BASIC in types_in_report
        assert LicenseType.ENTERPRISE in types_in_report

    def test_report_totals_consistent_with_splits(self) -> None:
        self.splitter.split(Decimal("100.00"), LicenseType.STANDARD)
        report = self.splitter.get_distribution_report()
        entry = next(e for e in report if e.license_type == LicenseType.STANDARD)
        total_allocated = (
            entry.total_to_platform + entry.total_to_creator + entry.total_to_validator + entry.total_to_reserve
        )
        # Should be close to total_collected (residual may be minimal)
        assert abs(total_allocated - entry.total_collected) < Decimal("0.01")

    def test_report_sorted_by_license_type_value(self) -> None:
        self.splitter.split(Decimal("10"), LicenseType.RESEARCH)
        self.splitter.split(Decimal("10"), LicenseType.BASIC)
        report = self.splitter.get_distribution_report()
        type_values = [e.license_type.value for e in report]
        assert type_values == sorted(type_values)
