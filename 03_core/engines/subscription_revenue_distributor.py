"""subscription_revenue_distributor.py — Non-custodial subscription revenue distribution.

Compute-only: produces revenue-share calculations and payout reports.
Never holds, stores, or transfers funds.
All operations produce SHA-256 evidence hashes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any


class DistributorError(Exception):
    pass


class ValidationError(DistributorError):
    pass


def _sha256_dict(data: dict[str, Any]) -> str:
    serialised = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RevenueShare:
    subscription_id: str
    total_revenue: str
    shares: dict[str, str]       # contributor_id -> allocated amount (decimal string)
    remainder: str
    evidence_hash: str
    input_hash: str


@dataclass(frozen=True)
class TieredTier:
    tier_name: str
    threshold: str
    rate: str
    allocated: str


@dataclass(frozen=True)
class TieredResult:
    total_revenue: str
    tiers_applied: list[TieredTier]
    total_allocated: str
    remainder: str
    evidence_hash: str
    input_hash: str


@dataclass(frozen=True)
class PayoutReport:
    period: str
    total_distributed: str
    distribution_count: int
    per_contributor: dict[str, str]   # contributor_id -> cumulative amount
    evidence_hash: str
    input_hash: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SubscriptionRevenueDistributor:
    """
    Calculates how subscription revenue should be distributed among contributors.

    Non-custodial: this class emits distribution instructions only.
    It never stores, holds, or transfers funds.
    """

    PRECISION: int = 8

    def _quantiser(self) -> Decimal:
        return Decimal(10) ** -self.PRECISION

    # ------------------------------------------------------------------
    # calculate_revenue_share
    # ------------------------------------------------------------------

    def calculate_revenue_share(
        self,
        subscription: dict[str, Any],
        contributors: dict[str, float | str],
    ) -> RevenueShare:
        """
        Distribute subscription revenue among contributors by weight.

        Args:
            subscription: Must contain 'id' (str) and 'revenue' (numeric).
            contributors: Mapping contributor_id -> weight (percentage, must sum to 100).

        Returns:
            RevenueShare with per-contributor allocated amounts.
        """
        sub_id = subscription.get("id")
        if not sub_id:
            raise ValidationError("subscription must have an 'id' field")
        revenue_raw = subscription.get("revenue")
        if revenue_raw is None:
            raise ValidationError("subscription must have a 'revenue' field")
        if not contributors:
            raise ValidationError("contributors must not be empty")

        revenue = Decimal(str(revenue_raw))
        if revenue <= 0:
            raise ValidationError("revenue must be positive")

        weight_sum = sum(Decimal(str(w)) for w in contributors.values())
        if not (Decimal("99.9999") <= weight_sum <= Decimal("100.0001")):
            raise ValidationError(f"contributor weights must sum to 100, got {weight_sum}")

        input_payload: dict[str, Any] = {
            "subscription_id": sub_id,
            "revenue": str(revenue_raw),
            "contributors": {k: str(v) for k, v in contributors.items()},
        }
        input_hash = _sha256_dict(input_payload)

        q = self._quantiser()
        shares: dict[str, str] = {}
        allocated = Decimal("0")
        contributor_list = list(contributors.items())

        for i, (cid, weight) in enumerate(contributor_list):
            if i == len(contributor_list) - 1:
                amount = revenue - allocated
            else:
                amount = (revenue * Decimal(str(weight)) / Decimal("100")).quantize(q, rounding=ROUND_DOWN)
            shares[cid] = str(amount)
            allocated += amount

        remainder = str(revenue - sum(Decimal(v) for v in shares.values()))

        output_payload: dict[str, Any] = {
            "subscription_id": sub_id,
            "total_revenue": str(revenue),
            "shares": shares,
            "remainder": remainder,
        }
        evidence_hash = _sha256_dict(output_payload)

        return RevenueShare(
            subscription_id=sub_id,
            total_revenue=str(revenue),
            shares=shares,
            remainder=remainder,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )

    # ------------------------------------------------------------------
    # apply_tiered_distribution
    # ------------------------------------------------------------------

    def apply_tiered_distribution(
        self,
        revenue: float | str,
        tiers: list[dict[str, Any]],
    ) -> TieredResult:
        """
        Apply tiered revenue distribution (e.g. escalating royalty rates).

        Each tier dict must have:
          - 'name' (str)
          - 'threshold' (numeric): upper bound of this tier (exclusive)
          - 'rate' (numeric): fraction 0.0 – 1.0 applied to the tier slice

        Tiers must be ordered from lowest to highest threshold.
        The last tier's threshold is treated as infinity.

        Args:
            revenue: Total revenue to distribute across tiers.
            tiers: Ordered list of tier definitions.

        Returns:
            TieredResult with per-tier allocation details.
        """
        if not tiers:
            raise ValidationError("tiers must not be empty")

        total = Decimal(str(revenue))
        if total <= 0:
            raise ValidationError("revenue must be positive")

        input_payload: dict[str, Any] = {
            "revenue": str(revenue),
            "tiers": [
                {"name": t.get("name"), "threshold": str(t.get("threshold", 0)), "rate": str(t.get("rate", 0))}
                for t in tiers
            ],
        }
        input_hash = _sha256_dict(input_payload)

        q = self._quantiser()
        tiers_applied: list[TieredTier] = []
        remaining = total
        prev_threshold = Decimal("0")

        for i, tier in enumerate(tiers):
            name = str(tier.get("name", f"tier_{i}"))
            raw_threshold = tier.get("threshold")
            rate = Decimal(str(tier.get("rate", "0")))

            if raw_threshold is None or i == len(tiers) - 1:
                tier_slice = remaining
                threshold_display = "infinity"
            else:
                threshold = Decimal(str(raw_threshold))
                tier_slice = min(remaining, max(Decimal("0"), threshold - prev_threshold))
                threshold_display = str(threshold)
                prev_threshold = threshold

            allocated = (tier_slice * rate).quantize(q, rounding=ROUND_DOWN)
            remaining -= tier_slice

            tiers_applied.append(
                TieredTier(
                    tier_name=name,
                    threshold=threshold_display,
                    rate=str(rate),
                    allocated=str(allocated),
                )
            )

            if remaining <= 0:
                break

        total_allocated = sum(Decimal(t.allocated) for t in tiers_applied)
        remainder = str(total - total_allocated)

        output_payload: dict[str, Any] = {
            "total_revenue": str(revenue),
            "tiers_applied": [
                {"tier": t.tier_name, "threshold": t.threshold, "rate": t.rate, "allocated": t.allocated}
                for t in tiers_applied
            ],
            "total_allocated": str(total_allocated),
            "remainder": remainder,
        }
        evidence_hash = _sha256_dict(output_payload)

        return TieredResult(
            total_revenue=str(revenue),
            tiers_applied=tiers_applied,
            total_allocated=str(total_allocated),
            remainder=remainder,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )

    # ------------------------------------------------------------------
    # generate_payout_report
    # ------------------------------------------------------------------

    def generate_payout_report(
        self,
        period: str,
        distributions: list[RevenueShare],
    ) -> PayoutReport:
        """
        Aggregate multiple RevenueShare results into a payout report for a period.

        Args:
            period: Human-readable period label, e.g. "2026-Q1".
            distributions: List of RevenueShare results to aggregate.

        Returns:
            PayoutReport with per-contributor cumulative totals and evidence hash.
        """
        if not period:
            raise ValidationError("period must not be empty")

        input_payload: dict[str, Any] = {
            "period": period,
            "distribution_count": len(distributions),
            "distribution_hashes": [d.evidence_hash for d in distributions],
        }
        input_hash = _sha256_dict(input_payload)

        per_contributor: dict[str, Decimal] = {}
        total_distributed = Decimal("0")

        for dist in distributions:
            for cid, amount_str in dist.shares.items():
                amount = Decimal(amount_str)
                per_contributor[cid] = per_contributor.get(cid, Decimal("0")) + amount
                total_distributed += amount

        per_contributor_str = {k: str(v) for k, v in per_contributor.items()}

        output_payload: dict[str, Any] = {
            "period": period,
            "total_distributed": str(total_distributed),
            "distribution_count": len(distributions),
            "per_contributor": per_contributor_str,
        }
        evidence_hash = _sha256_dict(output_payload)

        return PayoutReport(
            period=period,
            total_distributed=str(total_distributed),
            distribution_count=len(distributions),
            per_contributor=per_contributor_str,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )
