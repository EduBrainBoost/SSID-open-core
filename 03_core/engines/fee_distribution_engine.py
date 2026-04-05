"""fee_distribution_engine.py — Non-custodial fee distribution computation.

Compute-only: calculates distribution instructions but never holds funds.
All operations produce SHA-256 evidence hashes for audit traceability.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Any


class DistributionMode(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class FeeDistributionError(Exception):
    pass


class ValidationError(FeeDistributionError):
    pass


def _sha256_dict(data: dict[str, Any]) -> str:
    serialised = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


@dataclass(frozen=True)
class DistributionResult:
    distribution: dict[str, str]  # participant_id -> amount as decimal string
    mode: DistributionMode
    total_amount: str
    remainder: str
    evidence_hash: str
    input_hash: str


@dataclass
class FeeDistributionEngine:
    """
    Calculates how a total_amount should be distributed among participants.

    Non-custodial: this engine emits distribution instructions only.
    It never stores, holds, or transfers funds.
    """

    precision: int = 8  # decimal places

    def calculate_distribution(
        self,
        total_amount: float | str,
        participants: list[str],
        weights: dict[str, float | str],
        mode: DistributionMode = DistributionMode.PERCENTAGE,
    ) -> dict[str, str]:
        """
        Calculate distribution of total_amount among participants by weights.

        Args:
            total_amount: The amount to distribute (treated as an opaque numeric value).
            participants: Ordered list of participant IDs.
            weights: Mapping participant_id -> weight. For PERCENTAGE mode the
                     weights must sum to 100.0. For FIXED mode they are absolute
                     amounts and must sum to <= total_amount.
            mode: DistributionMode.PERCENTAGE or DistributionMode.FIXED.

        Returns:
            Mapping participant_id -> allocated amount as a decimal string.
        """
        if not participants:
            raise ValidationError("participants list must not be empty")
        if not weights:
            raise ValidationError("weights mapping must not be empty")
        missing = set(participants) - set(weights)
        if missing:
            raise ValidationError(f"weights missing for participants: {missing}")

        total = Decimal(str(total_amount))
        if total <= 0:
            raise ValidationError("total_amount must be positive")

        quantiser = Decimal(10) ** -self.precision

        if mode == DistributionMode.PERCENTAGE:
            return self._distribute_by_percentage(total, participants, weights, quantiser)
        elif mode == DistributionMode.FIXED:
            return self._distribute_by_fixed(total, participants, weights, quantiser)
        else:
            raise ValidationError(f"unknown mode: {mode}")

    def _distribute_by_percentage(
        self,
        total: Decimal,
        participants: list[str],
        weights: dict[str, float | str],
        quantiser: Decimal,
    ) -> dict[str, str]:
        weight_sum = sum(Decimal(str(w)) for w in weights.values())
        if not (Decimal("99.9999") <= weight_sum <= Decimal("100.0001")):
            raise ValidationError(f"percentage weights must sum to 100, got {weight_sum}")

        distribution: dict[str, str] = {}
        allocated = Decimal("0")
        for i, pid in enumerate(participants):
            if i == len(participants) - 1:
                # Last participant gets the remainder to avoid rounding loss.
                amount = total - allocated
            else:
                amount = (total * Decimal(str(weights[pid])) / Decimal("100")).quantize(quantiser, rounding=ROUND_DOWN)
            distribution[pid] = str(amount)
            allocated += amount
        return distribution

    def _distribute_by_fixed(
        self,
        total: Decimal,
        participants: list[str],
        weights: dict[str, float | str],
        quantiser: Decimal,
    ) -> dict[str, str]:
        fixed_sum = sum(Decimal(str(w)) for w in weights.values())
        if fixed_sum > total:
            raise ValidationError(f"fixed weights sum ({fixed_sum}) exceeds total_amount ({total})")
        distribution: dict[str, str] = {}
        for pid in participants:
            amount = Decimal(str(weights[pid])).quantize(quantiser, rounding=ROUND_DOWN)
            distribution[pid] = str(amount)
        return distribution

    def validate_distribution(self, distribution: dict[str, str]) -> bool:
        """
        Validate that all amounts in a distribution are positive decimals.

        Returns True when valid, raises ValidationError otherwise.
        """
        if not distribution:
            raise ValidationError("distribution must not be empty")
        for pid, amount_str in distribution.items():
            try:
                val = Decimal(amount_str)
            except Exception as exc:
                raise ValidationError(f"invalid amount '{amount_str}' for '{pid}'") from exc
            if val < 0:
                raise ValidationError(f"negative amount for participant '{pid}'")
        return True

    def apply_distribution(
        self,
        total_amount: float | str,
        participants: list[str],
        weights: dict[str, float | str],
        mode: DistributionMode = DistributionMode.PERCENTAGE,
    ) -> DistributionResult:
        """
        Full pipeline: calculate, validate, and wrap in an evidence-logged result.

        Returns a DistributionResult with SHA-256 hashes of input and output
        for non-repudiable audit evidence.
        """
        input_payload: dict[str, Any] = {
            "total_amount": str(total_amount),
            "participants": participants,
            "weights": {k: str(v) for k, v in weights.items()},
            "mode": mode.value,
        }
        input_hash = _sha256_dict(input_payload)

        distribution = self.calculate_distribution(total_amount, participants, weights, mode)
        self.validate_distribution(distribution)

        total = Decimal(str(total_amount))
        allocated = sum(Decimal(v) for v in distribution.values())
        remainder = str(total - allocated)

        output_payload: dict[str, Any] = {
            "distribution": distribution,
            "mode": mode.value,
            "total_amount": str(total_amount),
            "remainder": remainder,
        }
        evidence_hash = _sha256_dict(output_payload)

        return DistributionResult(
            distribution=distribution,
            mode=mode,
            total_amount=str(total_amount),
            remainder=remainder,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )
