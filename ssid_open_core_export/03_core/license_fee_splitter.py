"""license_fee_splitter — License fee splitting for the SSID network.

Splits collected license fees between platform, content creators, and
validators according to configurable split ratios per license type.
Supports per-license-type ratio overrides and provides detailed
distribution reports.

Registry import path (orchestrator):
    03_core.license_fee_splitter
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class LicenseType(StrEnum):
    """Canonical license types in the SSID licensing model."""

    BASIC = "basic"
    STANDARD = "standard"
    COMMERCIAL = "commercial"
    ENTERPRISE = "enterprise"
    RESEARCH = "research"


class SplitRecipient(StrEnum):
    """Recipients in a license fee split."""

    PLATFORM = "platform"
    CREATOR = "creator"
    VALIDATOR = "validator"
    RESERVE = "reserve"


@dataclass
class SplitRatios:
    """Configured split ratios for a license type.

    Attributes:
        platform: Fraction of fee going to the platform (0–1).
        creator: Fraction of fee going to content creators (0–1).
        validator: Fraction of fee going to validators (0–1).
        reserve: Fraction of fee going to the reserve pool (0–1).

    All fractions must sum to exactly 1.0.
    """

    platform: float
    creator: float
    validator: float
    reserve: float = 0.0

    def __post_init__(self) -> None:
        for attr in ("platform", "creator", "validator", "reserve"):
            val = getattr(self, attr)
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{attr} ratio must be in [0, 1], got {val}")
        total = self.platform + self.creator + self.validator + self.reserve
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"SplitRatios must sum to 1.0, got {total:.10f}")

    def as_dict(self) -> dict[SplitRecipient, float]:
        """Return ratios as a mapping from SplitRecipient to fraction."""
        return {
            SplitRecipient.PLATFORM: self.platform,
            SplitRecipient.CREATOR: self.creator,
            SplitRecipient.VALIDATOR: self.validator,
            SplitRecipient.RESERVE: self.reserve,
        }


@dataclass
class SplitResult:
    """Result of a single license fee split operation.

    Attributes:
        total_amount: Gross fee amount that was split.
        license_type: The license type governing this split.
        allocations: Mapping of SplitRecipient → allocated amount.
        residual: Unallocated remainder due to rounding (typically near-zero).
        ratios_used: The split ratios applied.
    """

    total_amount: Decimal
    license_type: LicenseType
    allocations: dict[SplitRecipient, Decimal]
    residual: Decimal = Decimal("0")
    ratios_used: SplitRatios | None = None


@dataclass
class DistributionReportEntry:
    """A single entry in a cumulative distribution report.

    Attributes:
        license_type: License type for this entry.
        total_collected: Total fee amount collected for this license type.
        total_to_platform: Total allocated to platform.
        total_to_creator: Total allocated to creators.
        total_to_validator: Total allocated to validators.
        total_to_reserve: Total allocated to reserve.
        split_count: Number of split operations included.
    """

    license_type: LicenseType
    total_collected: Decimal
    total_to_platform: Decimal
    total_to_creator: Decimal
    total_to_validator: Decimal
    total_to_reserve: Decimal
    split_count: int = 0


# ---------------------------------------------------------------------------
# Default split ratios per license type
# ---------------------------------------------------------------------------

DEFAULT_SPLIT_RATIOS: dict[LicenseType, SplitRatios] = {
    LicenseType.BASIC: SplitRatios(platform=0.50, creator=0.35, validator=0.10, reserve=0.05),
    LicenseType.STANDARD: SplitRatios(platform=0.40, creator=0.40, validator=0.15, reserve=0.05),
    LicenseType.COMMERCIAL: SplitRatios(platform=0.30, creator=0.45, validator=0.20, reserve=0.05),
    LicenseType.ENTERPRISE: SplitRatios(platform=0.25, creator=0.50, validator=0.20, reserve=0.05),
    LicenseType.RESEARCH: SplitRatios(platform=0.20, creator=0.55, validator=0.20, reserve=0.05),
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class LicenseFeeSplitter:
    """Splits license fees between platform, creators, validators, and reserve.

    Split ratios are configurable per license type. The splitter also
    maintains a running ledger of all splits performed, which can be
    queried via ``get_distribution_report()``.

    Usage::

        splitter = LicenseFeeSplitter()
        result = splitter.split(
            amount=Decimal("200.00"),
            license_type=LicenseType.COMMERCIAL,
        )
        print(result.allocations)

        # Reconfigure ratios for a specific type
        splitter.configure_ratios(
            LicenseType.ENTERPRISE,
            SplitRatios(platform=0.20, creator=0.55, validator=0.20, reserve=0.05),
        )

        report = splitter.get_distribution_report()
    """

    def __init__(
        self,
        ratios: dict[LicenseType, SplitRatios] | None = None,
    ) -> None:
        """Initialise the splitter.

        Args:
            ratios: Optional override for per-license-type split ratios.
                Missing license types fall back to ``DEFAULT_SPLIT_RATIOS``.
        """
        self._ratios: dict[LicenseType, SplitRatios] = dict(DEFAULT_SPLIT_RATIOS)
        if ratios:
            self._ratios.update(ratios)

        # Ledger: license_type → list of SplitResult
        self._ledger: dict[LicenseType, list[SplitResult]] = {lt: [] for lt in LicenseType}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split(
        self,
        amount: Decimal,
        license_type: LicenseType,
    ) -> SplitResult:
        """Split *amount* according to the ratios for *license_type*.

        Args:
            amount: Gross fee amount to split (must be >= 0).
            license_type: License type determining the split ratios.

        Returns:
            A ``SplitResult`` with per-recipient allocations.

        Raises:
            ValueError: If *amount* is negative or no ratios are configured
                for *license_type*.
        """
        if amount < Decimal("0"):
            raise ValueError("amount must not be negative")

        ratios = self._ratios.get(license_type)
        if ratios is None:
            raise ValueError(f"No split ratios configured for license type '{license_type}'")

        quantize_unit = Decimal("0.000001")
        ratio_map = ratios.as_dict()
        allocations: dict[SplitRecipient, Decimal] = {}
        allocated = Decimal("0")

        for recipient, fraction in ratio_map.items():
            share = (amount * Decimal(str(fraction))).quantize(quantize_unit, rounding=ROUND_HALF_UP)
            allocations[recipient] = share
            allocated += share

        residual = amount - allocated

        result = SplitResult(
            total_amount=amount,
            license_type=license_type,
            allocations=allocations,
            residual=residual,
            ratios_used=ratios,
        )
        self._ledger[license_type].append(result)
        return result

    def configure_ratios(
        self,
        license_type: LicenseType,
        ratios: SplitRatios,
    ) -> None:
        """Set (or replace) the split ratios for *license_type*.

        Args:
            license_type: The license type to configure.
            ratios: New split ratios. Must sum to 1.0.
        """
        self._ratios[license_type] = ratios

    def get_ratios(self, license_type: LicenseType) -> SplitRatios | None:
        """Return the currently configured ratios for *license_type*, or None."""
        return self._ratios.get(license_type)

    def get_distribution_report(self) -> list[DistributionReportEntry]:
        """Return a cumulative distribution report for all recorded splits.

        Returns:
            List of ``DistributionReportEntry`` objects, one per license type
            that has at least one recorded split. Results are sorted by
            license type value.
        """
        report: list[DistributionReportEntry] = []

        for license_type, splits in self._ledger.items():
            if not splits:
                continue

            total_collected = sum(s.total_amount for s in splits)
            total_platform = sum(s.allocations.get(SplitRecipient.PLATFORM, Decimal("0")) for s in splits)
            total_creator = sum(s.allocations.get(SplitRecipient.CREATOR, Decimal("0")) for s in splits)
            total_validator = sum(s.allocations.get(SplitRecipient.VALIDATOR, Decimal("0")) for s in splits)
            total_reserve = sum(s.allocations.get(SplitRecipient.RESERVE, Decimal("0")) for s in splits)

            report.append(
                DistributionReportEntry(
                    license_type=license_type,
                    total_collected=total_collected,
                    total_to_platform=total_platform,
                    total_to_creator=total_creator,
                    total_to_validator=total_validator,
                    total_to_reserve=total_reserve,
                    split_count=len(splits),
                )
            )

        report.sort(key=lambda e: e.license_type.value)
        return report


__all__ = [
    "LicenseFeeSplitter",
    "LicenseType",
    "SplitRatios",
    "SplitRecipient",
    "SplitResult",
    "DistributionReportEntry",
    "DEFAULT_SPLIT_RATIOS",
]
