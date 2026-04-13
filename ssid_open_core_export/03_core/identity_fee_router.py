"""identity_fee_router — Identity verification fee routing for the SSID network.

Routes identity verification fees to the appropriate validators based on
verification type, tracks per-validator earnings, and maintains a configurable
fee schedule for all supported verification types.

Registry import path (orchestrator):
    03_core.identity_fee_router
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class VerificationType(StrEnum):
    """Categories of identity verification supported by the SSID network."""

    EMAIL = "email"
    PHONE = "phone"
    GOVERNMENT_ID = "government_id"
    BIOMETRIC = "biometric"
    ADDRESS = "address"
    CREDENTIAL = "credential"


@dataclass
class ValidatorProfile:
    """A validator eligible to receive identity verification fees.

    Attributes:
        validator_id: Unique identifier for the validator.
        supported_types: Verification types this validator can handle.
        reliability_score: Normalised reliability score in [0.0, 1.0].
            Higher scores result in larger fee allocation when multiple
            validators share a verification type.
        address: Optional settlement address / account reference.
    """

    validator_id: str
    supported_types: list[VerificationType]
    reliability_score: float = 1.0
    address: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.reliability_score <= 1.0:
            raise ValueError(f"reliability_score must be in [0, 1], got {self.reliability_score}")
        if not self.supported_types:
            raise ValueError("supported_types must not be empty")


@dataclass
class RoutingResult:
    """Result of a single fee routing operation.

    Attributes:
        verification_type: The type of verification that triggered the fee.
        total_fee: Total fee amount routed.
        validator_allocations: Mapping of validator_id → allocated fee amount.
        platform_fee: Amount retained by the platform.
        residual: Unallocated remainder due to rounding (typically near-zero).
    """

    verification_type: VerificationType
    total_fee: Decimal
    validator_allocations: dict[str, Decimal]
    platform_fee: Decimal = Decimal("0")
    residual: Decimal = Decimal("0")


@dataclass
class FeeScheduleEntry:
    """A single entry in the identity verification fee schedule.

    Canonical fee model (SoT):
        total_fee = 3% of transaction value
        developer_reward = 1% (non-custodial, automatic on-chain)
        system_treasury = 2% (DAO-governed, 50% burned subject to caps)

    Attributes:
        verification_type: The verification type this entry covers.
        total_fee_percent: Total fee as percentage of transaction value (canonical: 3.0).
        developer_percent: Developer reward as percentage of tx value (canonical: 1.0).
        treasury_percent: System treasury as percentage of tx value (canonical: 2.0).
    """

    verification_type: VerificationType
    total_fee_percent: Decimal = Decimal("3.0")
    developer_percent: Decimal = Decimal("1.0")
    treasury_percent: Decimal = Decimal("2.0")

    def __post_init__(self) -> None:
        if self.total_fee_percent < Decimal("0"):
            raise ValueError("total_fee_percent must not be negative")
        expected = self.developer_percent + self.treasury_percent
        if abs(self.total_fee_percent - expected) > Decimal("0.001"):
            raise ValueError(
                f"total_fee_percent ({self.total_fee_percent}) must equal "
                f"developer_percent + treasury_percent ({expected})"
            )


# ---------------------------------------------------------------------------
# Default fee schedule
# ---------------------------------------------------------------------------

# Canonical fee model: 3% of transaction value for all verification types.
# Allocation: 1% developer reward, 2% system treasury.
# Per-type entries preserved for routing/auditing; all use canonical percentages.
DEFAULT_FEE_SCHEDULE: dict[VerificationType, FeeScheduleEntry] = {
    VerificationType.EMAIL: FeeScheduleEntry(VerificationType.EMAIL),
    VerificationType.PHONE: FeeScheduleEntry(VerificationType.PHONE),
    VerificationType.GOVERNMENT_ID: FeeScheduleEntry(VerificationType.GOVERNMENT_ID),
    VerificationType.BIOMETRIC: FeeScheduleEntry(VerificationType.BIOMETRIC),
    VerificationType.ADDRESS: FeeScheduleEntry(VerificationType.ADDRESS),
    VerificationType.CREDENTIAL: FeeScheduleEntry(VerificationType.CREDENTIAL),
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class IdentityFeeRouter:
    """Routes identity verification fees to validators in the SSID network.

    Canonical fee model (SoT):
        total_fee = 3% of transaction value
        1% → developer reward (non-custodial, automatic on-chain)
        2% → system treasury (DAO-governed, 50% burned subject to caps)

    When a verification request is completed, the router:
    1. Computes total_fee = 3% of transaction value.
    2. Splits into developer_fee (1%) and treasury_fee (2%).
    3. Distributes the developer pool proportionally by
       ``reliability_score`` among validators that support the type.

    The router maintains a running earnings ledger per validator, queryable
    via ``get_validator_earnings()``.

    Usage::

        router = IdentityFeeRouter()
        validators = [
            ValidatorProfile("v1", [VerificationType.EMAIL], reliability_score=0.9),
            ValidatorProfile("v2", [VerificationType.EMAIL], reliability_score=0.6),
        ]
        result = router.route_fee(
            verification_type=VerificationType.EMAIL,
            tx_value=Decimal("100.00"),
            eligible_validators=validators,
        )
        print(result.validator_allocations)
    """

    def __init__(
        self,
        fee_schedule: dict[VerificationType, FeeScheduleEntry] | None = None,
    ) -> None:
        """Initialise the router.

        Args:
            fee_schedule: Optional override for the fee schedule. Missing
                verification types fall back to ``DEFAULT_FEE_SCHEDULE``.
        """
        self._fee_schedule: dict[VerificationType, FeeScheduleEntry] = dict(DEFAULT_FEE_SCHEDULE)
        if fee_schedule:
            self._fee_schedule.update(fee_schedule)

        # Earnings ledger: validator_id → cumulative earnings
        self._validator_earnings: dict[str, Decimal] = {}

        # Routing history
        self._routing_history: list[RoutingResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route_fee(
        self,
        verification_type: VerificationType,
        tx_value: Decimal,
        eligible_validators: Sequence[ValidatorProfile] | None = None,
        *,
        amount: Decimal | None = None,
    ) -> RoutingResult:
        """Route canonical 3% fee for *verification_type* to eligible validators.

        Computes total fee as 3% of *tx_value*, then splits:
          - 1% developer reward → distributed to validators by reliability
          - 2% system treasury → DAO-governed pool (50% burned, with caps)

        Args:
            verification_type: The type of identity verification performed.
            tx_value: Transaction value to compute fees from (must be >= 0).
            eligible_validators: Validators to route fees to. Only those
                that support *verification_type* are considered. If None or
                empty, the full developer share is retained as platform fee.
            amount: DEPRECATED — ignored. Use tx_value instead.

        Returns:
            A ``RoutingResult`` with per-validator allocations.

        Raises:
            ValueError: If *tx_value* is negative.
        """
        if tx_value < Decimal("0"):
            raise ValueError("tx_value must not be negative")

        schedule_entry = self._fee_schedule.get(verification_type)
        total_pct = Decimal(str(schedule_entry.total_fee_percent if schedule_entry else Decimal("3.0"))) / Decimal(
            "100"
        )
        dev_pct = Decimal(str(schedule_entry.developer_percent if schedule_entry else Decimal("1.0"))) / Decimal("100")
        treasury_pct = Decimal(str(schedule_entry.treasury_percent if schedule_entry else Decimal("2.0"))) / Decimal(
            "100"
        )

        quantize_unit = Decimal("0.000001")

        effective_amount = (tx_value * total_pct).quantize(quantize_unit, rounding=ROUND_HALF_UP)
        platform_fee = (tx_value * treasury_pct).quantize(quantize_unit, rounding=ROUND_HALF_UP)
        validator_pool = (tx_value * dev_pct).quantize(quantize_unit, rounding=ROUND_HALF_UP)

        # Filter validators that support this verification type
        capable_validators: list[ValidatorProfile] = []
        if eligible_validators:
            capable_validators = [v for v in eligible_validators if verification_type in v.supported_types]

        validator_allocations: dict[str, Decimal] = {}
        allocated = Decimal("0")

        if capable_validators and validator_pool > Decimal("0"):
            total_reliability = sum(v.reliability_score for v in capable_validators)

            for validator in capable_validators:
                vid = validator.validator_id
                if total_reliability == 0.0:
                    share = Decimal("0")
                else:
                    ratio = Decimal(str(validator.reliability_score / total_reliability))
                    share = (validator_pool * ratio).quantize(quantize_unit, rounding=ROUND_HALF_UP)
                validator_allocations[vid] = share
                allocated += share

                # Update ledger
                self._validator_earnings[vid] = self._validator_earnings.get(vid, Decimal("0")) + share
        else:
            # No capable validators — validator pool absorbed into platform
            platform_fee += validator_pool
            allocated = Decimal("0")

        residual = validator_pool - allocated if capable_validators else Decimal("0")

        result = RoutingResult(
            verification_type=verification_type,
            total_fee=effective_amount,
            validator_allocations=validator_allocations,
            platform_fee=platform_fee,
            residual=residual,
        )
        self._routing_history.append(result)
        return result

    def get_validator_earnings(self, validator_id: str) -> Decimal:
        """Return cumulative earnings for *validator_id*.

        Args:
            validator_id: ID of the validator to query.

        Returns:
            Total earned amount. Returns ``Decimal("0")`` if the validator
            has no recorded earnings.
        """
        return self._validator_earnings.get(validator_id, Decimal("0"))

    def get_fee_schedule(self) -> dict[VerificationType, FeeScheduleEntry]:
        """Return a copy of the current fee schedule.

        Returns:
            Mapping of verification type → fee schedule entry.
        """
        return dict(self._fee_schedule)

    def update_fee_schedule(
        self,
        verification_type: VerificationType,
        entry: FeeScheduleEntry,
    ) -> None:
        """Add or replace a fee schedule entry.

        Args:
            verification_type: The verification type to configure.
            entry: New fee schedule entry.
        """
        self._fee_schedule[verification_type] = entry

    def get_routing_history(self) -> list[RoutingResult]:
        """Return the full history of routing operations (read-only copy)."""
        return list(self._routing_history)

    def get_all_validator_earnings(self) -> dict[str, Decimal]:
        """Return a copy of the full validator earnings ledger."""
        return dict(self._validator_earnings)


__all__ = [
    "IdentityFeeRouter",
    "ValidatorProfile",
    "VerificationType",
    "FeeScheduleEntry",
    "RoutingResult",
    "DEFAULT_FEE_SCHEDULE",
]
