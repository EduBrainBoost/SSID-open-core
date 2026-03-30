"""governance_reward_engine — Governance participation reward distribution for SSID.

Distributes governance participation rewards to network participants based on
their voting activity, proposal creation, and review contributions. Reward
amounts are proportional to computed governance activity scores.

Registry import path (orchestrator):
    03_core.governance_reward_engine
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class GovernanceActivityType(str, Enum):
    """Categories of governance activity that contribute to the activity score."""
    VOTE = "vote"
    PROPOSAL = "proposal"
    REVIEW = "review"
    DELEGATION = "delegation"


@dataclass
class GovernanceActivity:
    """A single recorded governance activity for a participant.

    Attributes:
        activity_type: The category of governance activity.
        weight: Contribution weight of this activity in [0.0, 10.0].
            Defaults to 1.0.
        epoch: Optional epoch/period identifier the activity belongs to.
    """
    activity_type: GovernanceActivityType
    weight: float = 1.0
    epoch: Optional[str] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.weight <= 10.0:
            raise ValueError(
                f"activity weight must be in [0.0, 10.0], got {self.weight}"
            )


@dataclass
class GovernanceParticipant:
    """A participant eligible for governance rewards.

    Attributes:
        participant_id: Unique identifier for the participant.
        activities: List of governance activities performed.
        address: Optional settlement address / account reference.
    """
    participant_id: str
    activities: List[GovernanceActivity] = field(default_factory=list)
    address: Optional[str] = None


@dataclass
class GovernanceRewardResult:
    """Result of a governance reward distribution run.

    Attributes:
        pool_amount: Total pool amount distributed.
        allocations: Mapping of participant_id → allocated reward amount.
        activity_scores: Mapping of participant_id → computed activity score.
        residual: Unallocated remainder due to rounding.
        epoch: Optional epoch/batch identifier.
    """
    pool_amount: Decimal
    allocations: Dict[str, Decimal]
    activity_scores: Dict[str, float]
    residual: Decimal = Decimal("0")
    epoch: Optional[str] = None


# ---------------------------------------------------------------------------
# Default activity type weights — how much each activity type contributes
# ---------------------------------------------------------------------------

DEFAULT_ACTIVITY_TYPE_WEIGHTS: Dict[GovernanceActivityType, float] = {
    GovernanceActivityType.VOTE: 1.0,
    GovernanceActivityType.PROPOSAL: 5.0,
    GovernanceActivityType.REVIEW: 3.0,
    GovernanceActivityType.DELEGATION: 0.5,
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class GovernanceRewardEngine:
    """Distributes governance participation rewards across SSID participants.

    The engine computes each participant's governance activity score as the
    sum of weighted activity contributions:

        score(p) = sum(activity_type_weight(a) * a.weight for a in p.activities)

    Rewards are then allocated proportionally to the activity scores.

    Usage::

        engine = GovernanceRewardEngine()
        participants = [
            GovernanceParticipant("alice", [
                GovernanceActivity(GovernanceActivityType.VOTE),
                GovernanceActivity(GovernanceActivityType.PROPOSAL),
            ]),
            GovernanceParticipant("bob", [
                GovernanceActivity(GovernanceActivityType.VOTE),
            ]),
        ]
        result = engine.distribute(
            pool_amount=Decimal("1000.00"),
            participants=participants,
        )
        print(result.allocations)
    """

    def __init__(
        self,
        activity_type_weights: Optional[Dict[GovernanceActivityType, float]] = None,
    ) -> None:
        """Initialise the engine.

        Args:
            activity_type_weights: Optional override for per-activity-type
                base weights. Falls back to ``DEFAULT_ACTIVITY_TYPE_WEIGHTS``
                when not provided.
        """
        self._activity_type_weights: Dict[GovernanceActivityType, float] = (
            activity_type_weights
            if activity_type_weights is not None
            else DEFAULT_ACTIVITY_TYPE_WEIGHTS
        )
        # Internal ledger: participant_id → list of activity records
        self._activity_ledger: Dict[str, List[GovernanceActivity]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_rewards(
        self,
        participants: Sequence[GovernanceParticipant],
        pool_amount: Decimal = Decimal("0"),
        epoch: Optional[str] = None,
    ) -> Dict[str, Decimal]:
        """Calculate (but do not distribute) reward amounts for *participants*.

        Args:
            participants: Participants to calculate rewards for.
            pool_amount: Total reward pool to allocate proportionally.
            epoch: Optional epoch identifier for reporting.

        Returns:
            Mapping of participant_id → calculated reward amount.

        Raises:
            ValueError: If *pool_amount* is negative or *participants* is empty.
        """
        if pool_amount < Decimal("0"):
            raise ValueError("pool_amount must not be negative")
        if not participants:
            raise ValueError("participants list must not be empty")

        scores = {p.participant_id: self.get_activity_score(p.participant_id, p)
                  for p in participants}
        total_score = sum(scores.values())
        quantize_unit = Decimal("0.000001")
        rewards: Dict[str, Decimal] = {}

        for participant in participants:
            pid = participant.participant_id
            if total_score == 0.0:
                rewards[pid] = Decimal("0")
            else:
                ratio = Decimal(str(scores[pid] / total_score))
                rewards[pid] = (pool_amount * ratio).quantize(
                    quantize_unit, rounding=ROUND_HALF_UP
                )

        return rewards

    def distribute(
        self,
        pool_amount: Decimal,
        participants: Sequence[GovernanceParticipant],
        epoch: Optional[str] = None,
    ) -> GovernanceRewardResult:
        """Distribute *pool_amount* governance rewards across *participants*.

        Args:
            pool_amount: Total reward pool to distribute (must be >= 0).
            participants: Governance participants eligible for rewards.
            epoch: Optional identifier for the distribution epoch/batch.

        Returns:
            A ``GovernanceRewardResult`` with per-participant allocations and
            activity scores.

        Raises:
            ValueError: If *pool_amount* is negative or *participants* is empty.
        """
        if pool_amount < Decimal("0"):
            raise ValueError("pool_amount must not be negative")
        if not participants:
            raise ValueError("participants list must not be empty")

        scores = {p.participant_id: self.get_activity_score(p.participant_id, p)
                  for p in participants}
        total_score = sum(scores.values())
        quantize_unit = Decimal("0.000001")
        allocations: Dict[str, Decimal] = {}
        allocated = Decimal("0")

        for participant in participants:
            pid = participant.participant_id
            if total_score == 0.0:
                share = Decimal("0")
            else:
                ratio = Decimal(str(scores[pid] / total_score))
                share = (pool_amount * ratio).quantize(
                    quantize_unit, rounding=ROUND_HALF_UP
                )
            allocations[pid] = share
            allocated += share

        residual = pool_amount - allocated

        return GovernanceRewardResult(
            pool_amount=pool_amount,
            allocations=allocations,
            activity_scores=scores,
            residual=residual,
            epoch=epoch,
        )

    def get_activity_score(
        self,
        participant_id: str,
        participant: Optional[GovernanceParticipant] = None,
    ) -> float:
        """Compute the governance activity score for *participant_id*.

        The score is the sum of (activity_type_base_weight * activity.weight)
        across all activities. If *participant* is provided, its activities
        are used directly; otherwise the internal ledger is consulted.

        Args:
            participant_id: ID of the participant to score.
            participant: Optional participant instance with activity list.
                If omitted, ledger data is used.

        Returns:
            Non-negative float activity score.
        """
        if participant is not None:
            activities = participant.activities
            # Merge into internal ledger for future lookups
            self._activity_ledger[participant_id] = list(activities)
        else:
            activities = self._activity_ledger.get(participant_id, [])

        return sum(
            self._activity_type_weights.get(a.activity_type, 1.0) * a.weight
            for a in activities
        )

    def record_activity(
        self,
        participant_id: str,
        activity: GovernanceActivity,
    ) -> None:
        """Record a single governance activity in the internal ledger.

        Args:
            participant_id: ID of the participant performing the activity.
            activity: The governance activity to record.
        """
        if participant_id not in self._activity_ledger:
            self._activity_ledger[participant_id] = []
        self._activity_ledger[participant_id].append(activity)

    def activity_type_weight(self, activity_type: GovernanceActivityType) -> float:
        """Return the configured base weight for *activity_type*."""
        return self._activity_type_weights.get(activity_type, 1.0)


__all__ = [
    "GovernanceRewardEngine",
    "GovernanceParticipant",
    "GovernanceActivity",
    "GovernanceRewardResult",
    "GovernanceActivityType",
    "DEFAULT_ACTIVITY_TYPE_WEIGHTS",
]
