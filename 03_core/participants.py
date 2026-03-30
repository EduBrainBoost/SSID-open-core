"""participants — FeeParticipant and RevenueParticipant models for the SSID network.

Defines the participant data models used throughout the fee-distribution and
revenue-sharing subsystems.  All records are non-custodial: the models carry
routing/accounting metadata only — no wallets, balances, or payment execution
happen here.

SoT v4.1.0 | ROOT-24-LOCK | Module: 03_core
Evidence strategy: hash_manifest_only
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ParticipantStatus(str, Enum):
    """Lifecycle status of a fee/revenue participant."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    RETIRED = "retired"


class FeeCategory(str, Enum):
    """Canonical fee boundary categories defined by the SSID SoT.

    Derived from SSID_structure_gebuehren_abo_modelle.md:
    - PEER:    Peer-to-peer transaction fees
    - PROOF:   Proof generation / verification fees
    - UTILITY: System utility / infrastructure fees
    - REWARD:  Governance and community reward allocations
    """
    PEER = "peer"
    PROOF = "proof"
    UTILITY = "utility"
    REWARD = "reward"


class RevenueCategory(str, Enum):
    """Revenue stream categories from the SSID subscription model (SoT v5.4.3).

    - SYSTEM_OPERATIONAL: 50% of subscription revenue — infrastructure costs
    - DAO_TREASURY:        30% — community governance grants
    - DEVELOPER_CORE:      10% — core-team development
    - INCENTIVE_RESERVE:   10% — merit-based node/user bonuses
    """
    SYSTEM_OPERATIONAL = "system_operational"
    DAO_TREASURY = "dao_treasury"
    DEVELOPER_CORE = "developer_core"
    INCENTIVE_RESERVE = "incentive_reserve"


# ---------------------------------------------------------------------------
# FeeParticipant
# ---------------------------------------------------------------------------

@dataclass
class FeeParticipant:
    """A participant in the SSID fee-collection system.

    Represents an entity (node, validator, platform component) that is
    eligible to receive a share of collected fees.  Eligibility is
    categorised by ``fee_categories`` and weighted by ``reliability_score``.

    Attributes:
        participant_id: Stable, unique identifier (DID or internal ID).
        display_name: Human-readable label for audit logs.
        fee_categories: Fee boundary categories this participant covers.
        reliability_score: Normalised weight in [0.0, 1.0]. Used by the
            fee-routing layer to pro-rate distributions among competing
            participants of the same category.
        status: Current lifecycle status.
        address: Optional settlement address / routing reference.
            Must NOT contain PII; use hash-reference or DID.
        metadata: Arbitrary key/value pairs for audit tagging. No PII.
    """

    participant_id: str
    display_name: str
    fee_categories: List[FeeCategory]
    reliability_score: float = 1.0
    status: ParticipantStatus = ParticipantStatus.ACTIVE
    address: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.participant_id:
            raise ValueError("participant_id must not be empty")
        if not self.display_name:
            raise ValueError("display_name must not be empty")
        if not self.fee_categories:
            raise ValueError("fee_categories must contain at least one entry")
        if not 0.0 <= self.reliability_score <= 1.0:
            raise ValueError(
                f"reliability_score must be in [0, 1], got {self.reliability_score}"
            )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_eligible_for(self, category: FeeCategory) -> bool:
        """Return True if this participant covers *category*."""
        return category in self.fee_categories

    def is_active(self) -> bool:
        """Return True if participant is in ACTIVE status."""
        return self.status == ParticipantStatus.ACTIVE

    # ------------------------------------------------------------------
    # Audit / evidence helpers
    # ------------------------------------------------------------------

    def to_audit_dict(self) -> Dict[str, object]:
        """Return a serialisable, PII-free dict for audit logging."""
        return {
            "participant_id": self.participant_id,
            "display_name": self.display_name,
            "fee_categories": [c.value for c in self.fee_categories],
            "reliability_score": self.reliability_score,
            "status": self.status.value,
            # address is intentionally omitted from audit output
            "metadata": dict(self.metadata),
        }

    def identity_hash(self) -> str:
        """Return SHA-256 of canonical participant identity (no PII).

        Used for non-custodial, hash-only audit evidence.
        """
        payload = json.dumps(
            {
                "participant_id": self.participant_id,
                "fee_categories": sorted(c.value for c in self.fee_categories),
                "reliability_score": str(self.reliability_score),
                "status": self.status.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# RevenueParticipant
# ---------------------------------------------------------------------------

@dataclass
class RevenueParticipant:
    """A participant in the SSID subscription revenue distribution system.

    Models an entity entitled to receive a share of subscription/license
    revenue according to the 50/30/10/10 split defined in the SSID SoT
    (subscription_revenue_distributor model).

    Attributes:
        participant_id: Stable, unique identifier.
        display_name: Human-readable label for audit logs.
        revenue_categories: Revenue stream categories this participant covers.
        allocation_ratio: Fraction of the category pool allocated to this
            participant, in [0.0, 1.0].  Multiple participants sharing the
            same category are pro-rated by this value.
        status: Current lifecycle status.
        vesting_days: Optional vesting horizon in days (0 = immediate).
            Mirrors the developer vesting schedule from SoT (90 days linear).
        metadata: Arbitrary key/value pairs for audit tagging. No PII.
    """

    participant_id: str
    display_name: str
    revenue_categories: List[RevenueCategory]
    allocation_ratio: float = 1.0
    status: ParticipantStatus = ParticipantStatus.ACTIVE
    vesting_days: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.participant_id:
            raise ValueError("participant_id must not be empty")
        if not self.display_name:
            raise ValueError("display_name must not be empty")
        if not self.revenue_categories:
            raise ValueError("revenue_categories must contain at least one entry")
        if not 0.0 <= self.allocation_ratio <= 1.0:
            raise ValueError(
                f"allocation_ratio must be in [0, 1], got {self.allocation_ratio}"
            )
        if self.vesting_days < 0:
            raise ValueError(
                f"vesting_days must be >= 0, got {self.vesting_days}"
            )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_eligible_for(self, category: RevenueCategory) -> bool:
        """Return True if this participant covers *category*."""
        return category in self.revenue_categories

    def is_active(self) -> bool:
        """Return True if participant is in ACTIVE status."""
        return self.status == ParticipantStatus.ACTIVE

    def has_vesting(self) -> bool:
        """Return True if this participant has a non-zero vesting schedule."""
        return self.vesting_days > 0

    # ------------------------------------------------------------------
    # Audit / evidence helpers
    # ------------------------------------------------------------------

    def to_audit_dict(self) -> Dict[str, object]:
        """Return a serialisable, PII-free dict for audit logging."""
        return {
            "participant_id": self.participant_id,
            "display_name": self.display_name,
            "revenue_categories": [c.value for c in self.revenue_categories],
            "allocation_ratio": self.allocation_ratio,
            "status": self.status.value,
            "vesting_days": self.vesting_days,
            "metadata": dict(self.metadata),
        }

    def identity_hash(self) -> str:
        """Return SHA-256 of canonical participant identity (no PII).

        Used for non-custodial, hash-only audit evidence.
        """
        payload = json.dumps(
            {
                "participant_id": self.participant_id,
                "revenue_categories": sorted(c.value for c in self.revenue_categories),
                "allocation_ratio": str(self.allocation_ratio),
                "status": self.status.value,
                "vesting_days": self.vesting_days,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Registry helper
# ---------------------------------------------------------------------------

class ParticipantRegistry:
    """In-memory registry for both FeeParticipants and RevenueParticipants.

    Provides lookup by participant_id and category-based filtering.
    The registry never stores settlement addresses or PII.
    """

    def __init__(self) -> None:
        self._fee: Dict[str, FeeParticipant] = {}
        self._revenue: Dict[str, RevenueParticipant] = {}

    # Fee participant management

    def register_fee_participant(self, p: FeeParticipant) -> None:
        """Register a FeeParticipant.  Raises ValueError on duplicate id."""
        if p.participant_id in self._fee:
            raise ValueError(
                f"FeeParticipant already registered: {p.participant_id}"
            )
        self._fee[p.participant_id] = p

    def get_fee_participant(self, participant_id: str) -> Optional[FeeParticipant]:
        """Return FeeParticipant by id, or None."""
        return self._fee.get(participant_id)

    def active_fee_participants(
        self, category: Optional[FeeCategory] = None
    ) -> List[FeeParticipant]:
        """Return active FeeParticipants, optionally filtered by category."""
        result = [p for p in self._fee.values() if p.is_active()]
        if category is not None:
            result = [p for p in result if p.is_eligible_for(category)]
        return result

    # Revenue participant management

    def register_revenue_participant(self, p: RevenueParticipant) -> None:
        """Register a RevenueParticipant.  Raises ValueError on duplicate id."""
        if p.participant_id in self._revenue:
            raise ValueError(
                f"RevenueParticipant already registered: {p.participant_id}"
            )
        self._revenue[p.participant_id] = p

    def get_revenue_participant(
        self, participant_id: str
    ) -> Optional[RevenueParticipant]:
        """Return RevenueParticipant by id, or None."""
        return self._revenue.get(participant_id)

    def active_revenue_participants(
        self, category: Optional[RevenueCategory] = None
    ) -> List[RevenueParticipant]:
        """Return active RevenueParticipants, optionally filtered by category."""
        result = [p for p in self._revenue.values() if p.is_active()]
        if category is not None:
            result = [p for p in result if p.is_eligible_for(category)]
        return result


__all__ = [
    "FeeParticipant",
    "RevenueParticipant",
    "ParticipantRegistry",
    "FeeCategory",
    "RevenueCategory",
    "ParticipantStatus",
]
