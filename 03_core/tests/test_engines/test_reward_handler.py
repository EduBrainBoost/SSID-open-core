"""Tests for RewardHandler.

Covers: calculate_reward, validate_reward_eligibility, batch_process_rewards,
evidence hashing, ineligible participants, edge cases, and determinism.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from reward_handler import (
    RewardHandler,
    ValidationError,
)


@pytest.fixture()
def handler() -> RewardHandler:
    return RewardHandler()


@pytest.fixture()
def basic_rules() -> dict:
    return {
        "base_amounts": {"contribution": "10.0", "review": "5.0"},
        "multipliers": {"contribution": "2.0", "review": "1.5"},
        "eligibility_criteria": {"min_score": 1},
    }


# ---------------------------------------------------------------------------
# Test 1: Eligible participant receives correct reward amount
# ---------------------------------------------------------------------------


def test_calculate_reward_eligible_participant(handler: RewardHandler, basic_rules: dict) -> None:
    activity = {"participant_id": "user-001", "type": "contribution", "score": 5, "quantity": 1}
    reward = handler.calculate_reward(activity, basic_rules)
    assert reward.eligible is True
    # base 10.0 * multiplier 2.0 * quantity 1 = 20.0
    assert Decimal(reward.final_amount) == Decimal("20.00000000")


# ---------------------------------------------------------------------------
# Test 2: Ineligible participant receives zero reward
# ---------------------------------------------------------------------------


def test_calculate_reward_ineligible_participant(handler: RewardHandler, basic_rules: dict) -> None:
    activity = {"participant_id": "user-002", "type": "contribution", "score": 0, "quantity": 3}
    reward = handler.calculate_reward(activity, basic_rules)
    assert reward.eligible is False
    assert Decimal(reward.final_amount) == Decimal("0")


# ---------------------------------------------------------------------------
# Test 3: Quantity multiplier scales reward correctly
# ---------------------------------------------------------------------------


def test_reward_scales_with_quantity(handler: RewardHandler) -> None:
    rules = {"base_amounts": {"action": "5"}, "multipliers": {"action": "1"}}
    activity = {"participant_id": "user-003", "type": "action", "quantity": 4}
    reward = handler.calculate_reward(activity, rules)
    assert Decimal(reward.final_amount) == Decimal("20.00000000")


# ---------------------------------------------------------------------------
# Test 4: Evidence hash is 64-char SHA-256 hex
# ---------------------------------------------------------------------------


def test_calculate_reward_evidence_hash_format(handler: RewardHandler, basic_rules: dict) -> None:
    activity = {"participant_id": "user-004", "type": "review", "score": 3}
    reward = handler.calculate_reward(activity, basic_rules)
    assert len(reward.evidence_hash) == 64
    assert len(reward.input_hash) == 64
    assert all(c in "0123456789abcdef" for c in reward.evidence_hash)


# ---------------------------------------------------------------------------
# Test 5: calculate_reward is deterministic
# ---------------------------------------------------------------------------


def test_calculate_reward_is_deterministic(handler: RewardHandler, basic_rules: dict) -> None:
    activity = {"participant_id": "user-005", "type": "review", "score": 10}
    r1 = handler.calculate_reward(activity, basic_rules)
    r2 = handler.calculate_reward(activity, basic_rules)
    assert r1.evidence_hash == r2.evidence_hash
    assert r1.final_amount == r2.final_amount


# ---------------------------------------------------------------------------
# Test 6: validate_reward_eligibility with min_ criteria
# ---------------------------------------------------------------------------


def test_validate_eligibility_min_criterion(handler: RewardHandler) -> None:
    criteria = {"min_reputation": 10}
    assert handler.validate_reward_eligibility({"reputation": 15}, criteria) is True
    assert handler.validate_reward_eligibility({"reputation": 5}, criteria) is False


# ---------------------------------------------------------------------------
# Test 7: validate_reward_eligibility with exact-match criterion
# ---------------------------------------------------------------------------


def test_validate_eligibility_exact_match(handler: RewardHandler) -> None:
    criteria = {"status": "active"}
    assert handler.validate_reward_eligibility({"status": "active"}, criteria) is True
    assert handler.validate_reward_eligibility({"status": "suspended"}, criteria) is False


# ---------------------------------------------------------------------------
# Test 8: batch_process_rewards aggregates totals correctly
# ---------------------------------------------------------------------------


def test_batch_process_rewards_totals(handler: RewardHandler) -> None:
    rules = {"base_amounts": {"task": "10"}, "multipliers": {"task": "1"}}
    activities = [
        {"participant_id": "u1", "type": "task"},
        {"participant_id": "u2", "type": "task"},
        {"participant_id": "u3", "type": "task"},
    ]
    batch = handler.batch_process_rewards(activities, rules)
    assert batch.total_rewards == 3
    assert Decimal(batch.total_amount) == Decimal("30.00000000")
    assert batch.eligible_count == 3
    assert batch.ineligible_count == 0


# ---------------------------------------------------------------------------
# Test 9: batch_process_rewards counts ineligible participants
# ---------------------------------------------------------------------------


def test_batch_process_rewards_ineligible_count(handler: RewardHandler) -> None:
    rules = {
        "base_amounts": {"task": "10"},
        "multipliers": {"task": "1"},
        "eligibility_criteria": {"min_level": 5},
    }
    activities = [
        {"participant_id": "u1", "type": "task", "level": 10},
        {"participant_id": "u2", "type": "task", "level": 2},
        {"participant_id": "u3", "type": "task", "level": 7},
    ]
    batch = handler.batch_process_rewards(activities, rules)
    assert batch.eligible_count == 2
    assert batch.ineligible_count == 1
    assert Decimal(batch.total_amount) == Decimal("20.00000000")


# ---------------------------------------------------------------------------
# Test 10: batch_process_rewards batch_evidence_hash is deterministic
# ---------------------------------------------------------------------------


def test_batch_evidence_hash_is_deterministic(handler: RewardHandler) -> None:
    rules = {"base_amounts": {"x": "1"}, "multipliers": {"x": "1"}}
    activities = [{"participant_id": "p1", "type": "x"}, {"participant_id": "p2", "type": "x"}]
    b1 = handler.batch_process_rewards(activities, rules)
    b2 = handler.batch_process_rewards(activities, rules)
    assert b1.batch_evidence_hash == b2.batch_evidence_hash


# ---------------------------------------------------------------------------
# Test 11: Missing participant_id raises ValidationError
# ---------------------------------------------------------------------------


def test_missing_participant_id_raises_error(handler: RewardHandler) -> None:
    with pytest.raises(ValidationError, match="participant_id"):
        handler.calculate_reward({"type": "task"}, {})


# ---------------------------------------------------------------------------
# Test 12: Empty activities list raises ValidationError
# ---------------------------------------------------------------------------


def test_empty_activities_raises_error(handler: RewardHandler) -> None:
    with pytest.raises(ValidationError, match="empty"):
        handler.batch_process_rewards([], {})
