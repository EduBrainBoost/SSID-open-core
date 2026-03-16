"""reward_handler.py — Non-custodial reward calculation and batch processing.

Compute-only: calculates reward amounts from activity data and rules.
Never stores, holds, or transfers funds.
All reward calculations produce SHA-256 evidence hashes.
No PII handling: participant IDs are treated as opaque references.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Any


class RewardError(Exception):
    pass


class EligibilityError(RewardError):
    pass


class ValidationError(RewardError):
    pass


def _sha256_dict(data: dict[str, Any]) -> str:
    serialised = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Reward:
    participant_id: str
    activity_type: str
    base_amount: str
    multiplier: str
    final_amount: str
    eligible: bool
    evidence_hash: str
    input_hash: str


@dataclass(frozen=True)
class RewardBatch:
    rewards: list[Reward]
    total_rewards: int
    eligible_count: int
    ineligible_count: int
    total_amount: str
    batch_evidence_hash: str
    input_hash: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RewardHandler:
    """
    Calculates rewards for participant activities based on configurable rules.

    Non-custodial: this class emits reward calculation results only.
    It never stores, holds, or transfers funds.
    """

    PRECISION: int = 8
    DEFAULT_MULTIPLIER: Decimal = Decimal("1.0")
    DEFAULT_BASE_AMOUNT: Decimal = Decimal("0")

    def _quantiser(self) -> Decimal:
        return Decimal(10) ** -self.PRECISION

    # ------------------------------------------------------------------
    # calculate_reward
    # ------------------------------------------------------------------

    def calculate_reward(
        self,
        activity: dict[str, Any],
        rules: dict[str, Any],
    ) -> Reward:
        """
        Calculate a single reward for an activity according to rules.

        Args:
            activity: Must contain 'participant_id' (str) and 'type' (str).
                      May contain 'quantity' (numeric, default 1).
            rules: Dict with optional keys:
                   - 'base_amounts': mapping activity_type -> base amount
                   - 'multipliers': mapping activity_type -> multiplier
                   - 'eligibility_criteria': dict of criteria for validate_reward_eligibility

        Returns:
            Reward dataclass with final_amount and evidence hash.
        """
        participant_id = activity.get("participant_id")
        if not participant_id:
            raise ValidationError("activity must have a 'participant_id' field")
        activity_type = activity.get("type")
        if not activity_type:
            raise ValidationError("activity must have a 'type' field")

        input_payload: dict[str, Any] = {
            "activity": {k: str(v) for k, v in activity.items()},
            "rules_hash": _sha256_dict(rules),
        }
        input_hash = _sha256_dict(input_payload)

        eligibility_criteria = rules.get("eligibility_criteria", {})
        eligible = self.validate_reward_eligibility(activity, eligibility_criteria)

        base_amounts: dict[str, Any] = rules.get("base_amounts", {})
        multipliers: dict[str, Any] = rules.get("multipliers", {})

        base_raw = base_amounts.get(activity_type, base_amounts.get("default", self.DEFAULT_BASE_AMOUNT))
        multiplier_raw = multipliers.get(activity_type, multipliers.get("default", self.DEFAULT_MULTIPLIER))
        quantity_raw = activity.get("quantity", 1)

        base = Decimal(str(base_raw))
        multiplier = Decimal(str(multiplier_raw))
        quantity = Decimal(str(quantity_raw))
        q = self._quantiser()

        if eligible:
            final = (base * multiplier * quantity).quantize(q, rounding=ROUND_DOWN)
        else:
            final = Decimal("0")

        output_payload: dict[str, Any] = {
            "participant_id": participant_id,
            "activity_type": activity_type,
            "base_amount": str(base),
            "multiplier": str(multiplier),
            "final_amount": str(final),
            "eligible": eligible,
        }
        evidence_hash = _sha256_dict(output_payload)

        return Reward(
            participant_id=participant_id,
            activity_type=activity_type,
            base_amount=str(base),
            multiplier=str(multiplier),
            final_amount=str(final),
            eligible=eligible,
            evidence_hash=evidence_hash,
            input_hash=input_hash,
        )

    # ------------------------------------------------------------------
    # validate_reward_eligibility
    # ------------------------------------------------------------------

    def validate_reward_eligibility(
        self,
        participant: dict[str, Any],
        criteria: dict[str, Any],
    ) -> bool:
        """
        Check whether a participant (or activity) meets eligibility criteria.

        Criteria keys map to expected values or threshold constraints:
          - Numeric values prefixed "min_<field>": participant[field] >= threshold
          - Numeric values prefixed "max_<field>": participant[field] <= threshold
          - Other keys: exact equality check against participant[key]

        Args:
            participant: Dict with participant / activity attributes.
            criteria: Dict of eligibility constraints.

        Returns:
            True if all criteria are satisfied, False otherwise.
            Raises EligibilityError only for structural problems.
        """
        if criteria is None:
            return True

        for key, threshold in criteria.items():
            if key.startswith("min_"):
                field = key[4:]
                val = participant.get(field)
                if val is None:
                    return False
                try:
                    if float(val) < float(threshold):
                        return False
                except (TypeError, ValueError):
                    return False
            elif key.startswith("max_"):
                field = key[4:]
                val = participant.get(field)
                if val is None:
                    return False
                try:
                    if float(val) > float(threshold):
                        return False
                except (TypeError, ValueError):
                    return False
            else:
                val = participant.get(key)
                if str(val) != str(threshold):
                    return False

        return True

    # ------------------------------------------------------------------
    # batch_process_rewards
    # ------------------------------------------------------------------

    def batch_process_rewards(
        self,
        activities: list[dict[str, Any]],
        rules: dict[str, Any],
    ) -> RewardBatch:
        """
        Process multiple activities and compute a batch reward result.

        Args:
            activities: List of activity dicts, each as per calculate_reward.
            rules: Shared rules dict applied to all activities.

        Returns:
            RewardBatch with individual rewards and aggregate statistics.
        """
        if not activities:
            raise ValidationError("activities must not be empty")

        input_payload: dict[str, Any] = {
            "activity_count": len(activities),
            "activities_hash": _sha256_dict(
                {"activities": [{k: str(v) for k, v in a.items()} for a in activities]}
            ),
            "rules_hash": _sha256_dict(rules),
        }
        input_hash = _sha256_dict(input_payload)

        rewards: list[Reward] = []
        for activity in activities:
            reward = self.calculate_reward(activity, rules)
            rewards.append(reward)

        eligible_count = sum(1 for r in rewards if r.eligible)
        ineligible_count = len(rewards) - eligible_count
        total_amount = sum(Decimal(r.final_amount) for r in rewards)

        batch_payload: dict[str, Any] = {
            "total_rewards": len(rewards),
            "eligible_count": eligible_count,
            "ineligible_count": ineligible_count,
            "total_amount": str(total_amount),
            "reward_hashes": [r.evidence_hash for r in rewards],
        }
        batch_evidence_hash = _sha256_dict(batch_payload)

        return RewardBatch(
            rewards=rewards,
            total_rewards=len(rewards),
            eligible_count=eligible_count,
            ineligible_count=ineligible_count,
            total_amount=str(total_amount),
            batch_evidence_hash=batch_evidence_hash,
            input_hash=input_hash,
        )
