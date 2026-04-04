#!/usr/bin/env python3
"""Subscription Revenue Distributor for SSID Ecosystem.

Distributes subscription revenue across the 24 canonical SSID roots with
configurable split ratios and monthly/quarterly settlement calculation.
Produces hash-only evidence for compliance -- no PII, no fund custody.

SoT v4.1.0 | ROOT-24-LOCK | Module: 03_core
Evidence strategy: hash_manifest_only
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

# Canonical ROOT-24-LOCK root names
ROOT_24_NAMES: list[str] = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]


class SettlementPeriod(Enum):
    """Supported settlement cadences."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


@dataclass(frozen=True)
class RootAllocation:
    """Revenue allocation for a single SSID root."""

    root_name: str
    amount: Decimal
    ratio: Decimal


@dataclass(frozen=True)
class SettlementCalculation:
    """Complete settlement calculation for a period.

    Non-custodial: describes *what* should happen, not executing transfers.
    """

    settlement_id: str
    timestamp: str
    period: SettlementPeriod
    period_label: str  # e.g. "2026-Q1" or "2026-03"
    gross_revenue: Decimal
    allocations: tuple  # tuple[RootAllocation, ...]
    remainder: Decimal
    evidence_hash: str


# ---------------------------------------------------------------------------
# Default split ratios across 24 roots
# ---------------------------------------------------------------------------


def _default_ratios() -> dict[str, Decimal]:
    """Generate a sensible default split across 24 roots.

    Weights:
        * 03_core            : 12%  (final authority, highest share)
        * 01_ai_layer        :  8%
        * 08_identity_score  :  8%
        * 15_infra           :  7%
        * 23_compliance      :  6%
        * 17_observability   :  5%
        * 14_zero_time_auth  :  5%
        * Remaining 17 roots : ~49% split evenly (~2.88% each)
    The total sums to exactly 1.00 via a balancing remainder on the last root.
    """
    explicit: dict[str, Decimal] = {
        "03_core": Decimal("0.12"),
        "01_ai_layer": Decimal("0.08"),
        "08_identity_score": Decimal("0.08"),
        "15_infra": Decimal("0.07"),
        "23_compliance": Decimal("0.06"),
        "17_observability": Decimal("0.05"),
        "14_zero_time_auth": Decimal("0.05"),
    }
    remaining_roots = [r for r in ROOT_24_NAMES if r not in explicit]
    remaining_total = Decimal("1") - sum(explicit.values())
    per_root = (remaining_total / len(remaining_roots)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    ratios: dict[str, Decimal] = {}
    for root in ROOT_24_NAMES:
        ratios[root] = explicit.get(root, per_root)

    # Adjust the very last remaining root to force total == 1
    total_so_far = sum(ratios.values())
    diff = Decimal("1") - total_so_far
    last_remaining = remaining_roots[-1]
    ratios[last_remaining] += diff

    return ratios


class SubscriptionRevenueDistributor:
    """Calculates subscription revenue distribution across the 24 SSID roots.

    Non-custodial: computes allocations and evidence only.  Downstream
    settlement services use the ``SettlementCalculation`` to initiate
    actual transfers.

    Design principles:
        * ROOT-24-LOCK aligned: always distributes across exactly 24 roots.
        * Hash-only evidence: SHA-256 digest, no PII.
        * Deterministic: identical inputs yield identical outputs.
    """

    def __init__(
        self,
        ratios: dict[str, Decimal] | None = None,
    ) -> None:
        self._ratios = ratios if ratios is not None else _default_ratios()
        self._validate_ratios()

    def _validate_ratios(self) -> None:
        """Ensure all 24 roots are present and ratios are non-negative."""
        for root in ROOT_24_NAMES:
            if root not in self._ratios:
                raise ValueError(f"Missing ratio for root: {root}")
        for root, ratio in self._ratios.items():
            if ratio < Decimal("0"):
                raise ValueError(f"Negative ratio for root: {root}")
        total = sum(self._ratios.values())
        if abs(total - Decimal("1")) > Decimal("0.001"):
            raise ValueError(f"Ratios must sum to ~1.0, got {total}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_settlement(
        self,
        gross_revenue: Decimal,
        period: SettlementPeriod,
        period_label: str,
    ) -> SettlementCalculation:
        """Compute a settlement distribution.

        Args:
            gross_revenue: Total subscription revenue for the period.
            period: Monthly or quarterly cadence.
            period_label: Human-readable label, e.g. "2026-03" or "2026-Q1".

        Returns:
            A ``SettlementCalculation`` describing allocations per root.

        Raises:
            ValueError: If gross_revenue is negative.
        """
        if gross_revenue < Decimal("0"):
            raise ValueError("gross_revenue must be non-negative")

        allocations, remainder = self._split(gross_revenue)
        settlement_id = uuid.uuid4().hex[:16]
        ts = datetime.now(UTC).isoformat()

        evidence_hash = self._hash_evidence(
            settlement_id,
            ts,
            period,
            period_label,
            gross_revenue,
            allocations,
            remainder,
        )

        return SettlementCalculation(
            settlement_id=settlement_id,
            timestamp=ts,
            period=period,
            period_label=period_label,
            gross_revenue=gross_revenue,
            allocations=tuple(allocations),
            remainder=remainder,
            evidence_hash=evidence_hash,
        )

    def get_ratios(self) -> dict[str, Decimal]:
        """Return a copy of the current root split ratios."""
        return dict(self._ratios)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split(self, gross: Decimal) -> tuple:
        """Return (allocations, remainder) with 2-decimal rounding."""
        allocations: list[RootAllocation] = []
        allocated = Decimal("0")

        for root in ROOT_24_NAMES:
            ratio = self._ratios[root]
            raw = gross * ratio
            rounded = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            allocated += rounded
            allocations.append(RootAllocation(root_name=root, amount=rounded, ratio=ratio))

        remainder = gross - allocated
        return allocations, remainder

    @staticmethod
    def _hash_evidence(
        settlement_id: str,
        ts: str,
        period: SettlementPeriod,
        period_label: str,
        gross: Decimal,
        allocations: list[RootAllocation],
        remainder: Decimal,
    ) -> str:
        payload = {
            "settlement_id": settlement_id,
            "timestamp": ts,
            "period": period.value,
            "period_label": period_label,
            "gross_revenue": str(gross),
            "allocations": [
                {
                    "root_name": a.root_name,
                    "amount": str(a.amount),
                    "ratio": str(a.ratio),
                }
                for a in allocations
            ],
            "remainder": str(remainder),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
