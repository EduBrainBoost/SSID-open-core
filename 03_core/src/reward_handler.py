"""reward_handler — Reward calculation and distribution for SSID participants.

Computes per-participant rewards based on action type, contribution quality,
and governance-defined reward schedules. Acts as the single authoritative
entry point for reward events in the SSID network.

Registry import path (orchestrator):
    03_core.src.reward_handler
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Sequence
import datetime


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class RewardAction(str, Enum):
    """Canonical reward-eligible actions in the SSID network."""
    IDENTITY_VERIFICATION = "identity_verification"
    DATA_PROVISION = "data_provision"
    GOVERNANCE_VOTE = "governance_vote"
    REFERRAL = "referral"
    AUDIT_CONTRIBUTION = "audit_contribution"
    STAKING = "staking"


@dataclass
class RewardEvent:
    """A single reward-triggering event.

    Attributes:
        event_id: Unique event identifier.
        participant_id: Identifier of the rewarded participant.
        action: The action type that triggered the reward.
        quality_score: Normalised quality indicator in [0.0, 1.0].
        quantity: Quantity of the action (e.g., number of verifications).
        timestamp: UTC timestamp of the event.
    """
    event_id: str
    participant_id: str
    action: RewardAction
    quality_score: float
    quantity: int = 1
    timestamp: Optional[datetime.datetime] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be in [0, 1], got {self.quality_score}"
            )
        if self.quantity < 1:
            raise ValueError(f"quantity must be >= 1, got {self.quantity}")
        if self.timestamp is None:
            self.timestamp = datetime.datetime.now(datetime.timezone.utc)


@dataclass
class RewardAllocation:
    """Computed reward for a single event.

    Attributes:
        event_id: Source event identifier.
        participant_id: Recipient participant.
        action: Reward-triggering action.
        base_reward: Reward before quality multiplier.
        quality_multiplier: Applied quality multiplier.
        final_reward: Actual reward credited.
    """
    event_id: str
    participant_id: str
    action: RewardAction
    base_reward: Decimal
    quality_multiplier: Decimal
    final_reward: Decimal


@dataclass
class RewardBatchResult:
    """Aggregated result of a batch reward calculation.

    Attributes:
        allocations: Per-event reward allocations.
        total_rewarded: Sum of all final_reward values.
        participant_totals: Per-participant cumulative reward.
    """
    allocations: List[RewardAllocation]
    total_rewarded: Decimal
    participant_totals: Dict[str, Decimal]


# ---------------------------------------------------------------------------
# Default reward schedule (base reward per action unit)
# ---------------------------------------------------------------------------
DEFAULT_REWARD_SCHEDULE: Dict[RewardAction, Decimal] = {
    RewardAction.IDENTITY_VERIFICATION: Decimal("1.00"),
    RewardAction.DATA_PROVISION: Decimal("0.50"),
    RewardAction.GOVERNANCE_VOTE: Decimal("0.25"),
    RewardAction.REFERRAL: Decimal("2.00"),
    RewardAction.AUDIT_CONTRIBUTION: Decimal("1.50"),
    RewardAction.STAKING: Decimal("0.10"),
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RewardHandler:
    """Calculates and aggregates rewards for SSID network participants.

    Reward formula per event::

        final_reward = base_reward(action) * quantity * quality_score

    Usage::

        handler = RewardHandler()
        events = [
            RewardEvent("evt-1", "alice", RewardAction.GOVERNANCE_VOTE, 0.9),
            RewardEvent("evt-2", "bob", RewardAction.DATA_PROVISION, 0.75, quantity=3),
        ]
        result = handler.calculate_batch(events)
        print(result.participant_totals)
    """

    def __init__(
        self,
        reward_schedule: Optional[Dict[RewardAction, Decimal]] = None,
    ) -> None:
        """Initialise the handler.

        Args:
            reward_schedule: Optional override for per-action base rewards.
                Falls back to ``DEFAULT_REWARD_SCHEDULE``.
        """
        self._schedule = (
            reward_schedule if reward_schedule is not None else DEFAULT_REWARD_SCHEDULE
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self, event: RewardEvent) -> RewardAllocation:
        """Calculate reward for a single *event*.

        Args:
            event: The reward-triggering event.

        Returns:
            A ``RewardAllocation`` with computed amounts.
        """
        base = self._schedule.get(event.action, Decimal("0"))
        multiplier = Decimal(str(event.quality_score))
        quantity = Decimal(str(event.quantity))
        final = (base * quantity * multiplier).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        return RewardAllocation(
            event_id=event.event_id,
            participant_id=event.participant_id,
            action=event.action,
            base_reward=base * quantity,
            quality_multiplier=multiplier,
            final_reward=final,
        )

    def calculate_batch(self, events: Sequence[RewardEvent]) -> RewardBatchResult:
        """Calculate rewards for a sequence of *events*.

        Args:
            events: Sequence of reward events to process.

        Returns:
            A ``RewardBatchResult`` with per-event allocations and totals.
        """
        allocations: List[RewardAllocation] = [self.calculate(e) for e in events]
        participant_totals: Dict[str, Decimal] = {}
        total = Decimal("0")
        for alloc in allocations:
            participant_totals[alloc.participant_id] = (
                participant_totals.get(alloc.participant_id, Decimal("0"))
                + alloc.final_reward
            )
            total += alloc.final_reward

        return RewardBatchResult(
            allocations=allocations,
            total_rewarded=total,
            participant_totals=participant_totals,
        )

    def base_reward(self, action: RewardAction) -> Decimal:
        """Return configured base reward for *action*."""
        return self._schedule.get(action, Decimal("0"))


__all__ = [
    "RewardHandler",
    "RewardEvent",
    "RewardAllocation",
    "RewardBatchResult",
    "RewardAction",
    "DEFAULT_REWARD_SCHEDULE",
]
