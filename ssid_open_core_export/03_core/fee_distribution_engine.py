#!/usr/bin/env python3
"""Fee Distribution Engine for SSID Ecosystem.

Non-custodial fee distribution calculator. Computes how subscription revenue
should be split among stakeholders (platform, operators, creators) using
configurable tiered fee structures. Produces hash-only evidence for audit
trails -- never stores or transfers actual funds.

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


class StakeholderRole(Enum):
    """Roles that receive a share of fee distributions."""

    PLATFORM = "platform"
    OPERATOR = "operator"
    CREATOR = "creator"
    RESERVE = "reserve"


@dataclass(frozen=True)
class FeeAllocation:
    """A single stakeholder's computed share of a fee distribution.

    All monetary values are Decimal to avoid floating-point drift.
    """

    stakeholder_id: str
    role: StakeholderRole
    amount: Decimal
    ratio: Decimal
    tier_name: str


@dataclass(frozen=True)
class DistributionResult:
    """Complete result of a fee distribution calculation.

    Contains allocations per stakeholder and hash-only evidence.
    """

    distribution_id: str
    timestamp: str
    gross_amount: Decimal
    allocations: tuple  # tuple[FeeAllocation, ...]
    evidence_hash: str
    remainder: Decimal  # rounding remainder kept in reserve


@dataclass
class TierRule:
    """Defines split ratios for a revenue tier.

    Attributes:
        name: Human-readable tier name.
        threshold_min: Minimum gross amount (inclusive) for this tier.
        threshold_max: Maximum gross amount (exclusive), None = unbounded.
        splits: Mapping of StakeholderRole -> Decimal ratio.  Must sum to 1.
    """

    name: str
    threshold_min: Decimal
    threshold_max: Decimal | None
    splits: dict[StakeholderRole, Decimal]

    def __post_init__(self) -> None:
        total = sum(self.splits.values())
        if total != Decimal("1"):
            raise ValueError(f"Tier '{self.name}' splits must sum to 1, got {total}")
        for role, ratio in self.splits.items():
            if ratio < Decimal("0"):
                raise ValueError(f"Tier '{self.name}' has negative ratio for {role.value}")

    def matches(self, amount: Decimal) -> bool:
        """Return True if *amount* falls within this tier's range."""
        if amount < self.threshold_min:
            return False
        return not (self.threshold_max is not None and amount >= self.threshold_max)


# ---------------------------------------------------------------------------
# Default tiers -- callers can override via FeeDistributionEngine.__init__
# ---------------------------------------------------------------------------
DEFAULT_TIERS: list[TierRule] = [
    TierRule(
        name="micro",
        threshold_min=Decimal("0"),
        threshold_max=Decimal("100"),
        splits={
            StakeholderRole.PLATFORM: Decimal("0.30"),
            StakeholderRole.OPERATOR: Decimal("0.40"),
            StakeholderRole.CREATOR: Decimal("0.25"),
            StakeholderRole.RESERVE: Decimal("0.05"),
        },
    ),
    TierRule(
        name="standard",
        threshold_min=Decimal("100"),
        threshold_max=Decimal("10000"),
        splits={
            StakeholderRole.PLATFORM: Decimal("0.25"),
            StakeholderRole.OPERATOR: Decimal("0.35"),
            StakeholderRole.CREATOR: Decimal("0.30"),
            StakeholderRole.RESERVE: Decimal("0.10"),
        },
    ),
    TierRule(
        name="enterprise",
        threshold_min=Decimal("10000"),
        threshold_max=None,
        splits={
            StakeholderRole.PLATFORM: Decimal("0.20"),
            StakeholderRole.OPERATOR: Decimal("0.30"),
            StakeholderRole.CREATOR: Decimal("0.35"),
            StakeholderRole.RESERVE: Decimal("0.15"),
        },
    ),
]


class FeeDistributionEngine:
    """Non-custodial fee distribution calculator.

    This engine computes allocation amounts per stakeholder given a gross
    revenue figure.  It does **not** execute transfers -- downstream settlement
    services consume the ``DistributionResult`` to initiate actual payments.

    Design principles:
        * Non-custodial: calculations only, no wallets / balances.
        * Hash-only evidence: the evidence_hash in the result is a SHA-256
          digest of the canonical JSON representation.  No PII is stored.
        * Deterministic: same inputs always produce the same outputs.
    """

    def __init__(
        self,
        tiers: list[TierRule] | None = None,
        stakeholder_ids: dict[StakeholderRole, str] | None = None,
    ) -> None:
        self._tiers = tiers if tiers is not None else list(DEFAULT_TIERS)
        self._stakeholder_ids = stakeholder_ids or {
            StakeholderRole.PLATFORM: "platform_default",
            StakeholderRole.OPERATOR: "operator_default",
            StakeholderRole.CREATOR: "creator_default",
            StakeholderRole.RESERVE: "reserve_default",
        }
        # Sort tiers by threshold_min ascending for deterministic matching.
        self._tiers.sort(key=lambda t: t.threshold_min)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self, gross_amount: Decimal) -> DistributionResult:
        """Compute fee distribution for *gross_amount*.

        Args:
            gross_amount: Total revenue to distribute (must be >= 0).

        Returns:
            A ``DistributionResult`` with per-stakeholder allocations.

        Raises:
            ValueError: If gross_amount is negative or no tier matches.
        """
        if gross_amount < Decimal("0"):
            raise ValueError("gross_amount must be non-negative")

        tier = self._resolve_tier(gross_amount)
        allocations, remainder = self._split(gross_amount, tier)

        dist_id = uuid.uuid4().hex[:16]
        ts = datetime.now(UTC).isoformat()

        evidence_hash = self._hash_evidence(
            dist_id,
            ts,
            gross_amount,
            allocations,
            remainder,
            tier.name,
        )

        return DistributionResult(
            distribution_id=dist_id,
            timestamp=ts,
            gross_amount=gross_amount,
            allocations=tuple(allocations),
            evidence_hash=evidence_hash,
            remainder=remainder,
        )

    def list_tiers(self) -> list[TierRule]:
        """Return a copy of the configured tiers."""
        return list(self._tiers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_tier(self, amount: Decimal) -> TierRule:
        for tier in self._tiers:
            if tier.matches(amount):
                return tier
        raise ValueError(f"No tier matched amount {amount}")

    def _split(self, gross: Decimal, tier: TierRule) -> tuple:
        """Return (allocations_list, remainder) with 2-decimal rounding."""
        allocations: list[FeeAllocation] = []
        allocated = Decimal("0")

        roles = sorted(tier.splits.keys(), key=lambda r: r.value)
        for role in roles:
            ratio = tier.splits[role]
            raw = gross * ratio
            rounded = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            allocated += rounded
            allocations.append(
                FeeAllocation(
                    stakeholder_id=self._stakeholder_ids.get(role, role.value),
                    role=role,
                    amount=rounded,
                    ratio=ratio,
                    tier_name=tier.name,
                )
            )

        remainder = gross - allocated
        return allocations, remainder

    @staticmethod
    def _hash_evidence(
        dist_id: str,
        ts: str,
        gross: Decimal,
        allocations: list[FeeAllocation],
        remainder: Decimal,
        tier_name: str,
    ) -> str:
        """Produce a SHA-256 hash of the distribution for audit evidence."""
        payload = {
            "distribution_id": dist_id,
            "timestamp": ts,
            "gross_amount": str(gross),
            "tier": tier_name,
            "allocations": [
                {
                    "stakeholder_id": a.stakeholder_id,
                    "role": a.role.value,
                    "amount": str(a.amount),
                    "ratio": str(a.ratio),
                }
                for a in allocations
            ],
            "remainder": str(remainder),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
