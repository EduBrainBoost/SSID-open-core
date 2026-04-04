"""Functional tests for 03_core/src/reward_handler.py."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from reward_handler import (  # type: ignore[import]
    DEFAULT_REWARD_SCHEDULE,
    RewardAction,
    RewardEvent,
    RewardHandler,
)


class TestRewardHandlerCalculate:
    def setup_method(self):
        self.handler = RewardHandler()

    def test_basic_reward_calculation(self):
        event = RewardEvent("e1", "alice", RewardAction.GOVERNANCE_VOTE, 1.0)
        alloc = self.handler.calculate(event)
        assert alloc.final_reward == DEFAULT_REWARD_SCHEDULE[RewardAction.GOVERNANCE_VOTE]

    def test_quality_score_scales_reward(self):
        full = self.handler.calculate(RewardEvent("e1", "alice", RewardAction.DATA_PROVISION, 1.0))
        half = self.handler.calculate(RewardEvent("e2", "alice", RewardAction.DATA_PROVISION, 0.5))
        assert abs(float(full.final_reward) - float(half.final_reward) * 2) < 0.001

    def test_quantity_multiplies_base(self):
        single = self.handler.calculate(RewardEvent("e1", "alice", RewardAction.IDENTITY_VERIFICATION, 1.0, quantity=1))
        triple = self.handler.calculate(RewardEvent("e2", "alice", RewardAction.IDENTITY_VERIFICATION, 1.0, quantity=3))
        assert abs(float(triple.final_reward) - float(single.final_reward) * 3) < 0.001

    def test_zero_quality_yields_zero_reward(self):
        alloc = self.handler.calculate(RewardEvent("e1", "alice", RewardAction.STAKING, 0.0))
        assert alloc.final_reward == Decimal("0")

    def test_invalid_quality_score_raises(self):
        with pytest.raises(ValueError, match="quality_score"):
            RewardEvent("e1", "alice", RewardAction.REFERRAL, 1.5)

    def test_invalid_quantity_raises(self):
        with pytest.raises(ValueError, match="quantity"):
            RewardEvent("e1", "alice", RewardAction.REFERRAL, 0.5, quantity=0)


class TestRewardHandlerBatch:
    def setup_method(self):
        self.handler = RewardHandler()

    def test_batch_aggregates_correctly(self):
        events = [
            RewardEvent("e1", "alice", RewardAction.GOVERNANCE_VOTE, 0.9),
            RewardEvent("e2", "alice", RewardAction.DATA_PROVISION, 0.75),
            RewardEvent("e3", "bob", RewardAction.REFERRAL, 1.0),
        ]
        result = self.handler.calculate_batch(events)
        assert len(result.allocations) == 3
        assert "alice" in result.participant_totals
        assert "bob" in result.participant_totals
        expected_total = sum(a.final_reward for a in result.allocations)
        assert result.total_rewarded == expected_total

    def test_empty_batch_returns_zero_total(self):
        result = self.handler.calculate_batch([])
        assert result.total_rewarded == Decimal("0")
        assert result.allocations == []

    def test_custom_schedule_applied(self):
        custom_schedule = {RewardAction.STAKING: Decimal("100.00")}
        handler = RewardHandler(reward_schedule=custom_schedule)
        alloc = handler.calculate(RewardEvent("e1", "x", RewardAction.STAKING, 1.0))
        assert alloc.final_reward == Decimal("100.00")
