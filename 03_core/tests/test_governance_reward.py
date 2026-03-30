"""Tests for governance_reward_engine."""
from __future__ import annotations

from decimal import Decimal

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_reward_engine import (
    GovernanceRewardEngine,
    GovernanceParticipant,
    GovernanceActivity,
    GovernanceRewardResult,
    GovernanceActivityType,
    DEFAULT_ACTIVITY_TYPE_WEIGHTS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _voter(pid: str) -> GovernanceParticipant:
    return GovernanceParticipant(
        pid,
        [GovernanceActivity(GovernanceActivityType.VOTE)],
    )


def _proposer(pid: str) -> GovernanceParticipant:
    return GovernanceParticipant(
        pid,
        [GovernanceActivity(GovernanceActivityType.PROPOSAL)],
    )


# ---------------------------------------------------------------------------
# GovernanceActivity validation
# ---------------------------------------------------------------------------

class TestGovernanceActivity:
    def test_valid_activity_default_weight(self) -> None:
        a = GovernanceActivity(GovernanceActivityType.VOTE)
        assert a.weight == 1.0

    def test_valid_activity_custom_weight(self) -> None:
        a = GovernanceActivity(GovernanceActivityType.PROPOSAL, weight=3.5)
        assert a.weight == 3.5

    def test_weight_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="weight"):
            GovernanceActivity(GovernanceActivityType.VOTE, weight=11.0)

    def test_weight_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            GovernanceActivity(GovernanceActivityType.REVIEW, weight=-1.0)

    def test_epoch_stored(self) -> None:
        a = GovernanceActivity(GovernanceActivityType.VOTE, epoch="2026-Q1")
        assert a.epoch == "2026-Q1"


# ---------------------------------------------------------------------------
# get_activity_score
# ---------------------------------------------------------------------------

class TestGetActivityScore:
    def setup_method(self) -> None:
        self.engine = GovernanceRewardEngine()

    def test_single_vote_score(self) -> None:
        p = _voter("alice")
        score = self.engine.get_activity_score("alice", p)
        expected = DEFAULT_ACTIVITY_TYPE_WEIGHTS[GovernanceActivityType.VOTE] * 1.0
        assert score == pytest.approx(expected)

    def test_proposal_score_higher_than_vote(self) -> None:
        voter = _voter("alice")
        proposer = _proposer("bob")
        score_vote = self.engine.get_activity_score("alice", voter)
        score_proposal = self.engine.get_activity_score("bob", proposer)
        assert score_proposal > score_vote

    def test_no_activities_score_zero(self) -> None:
        p = GovernanceParticipant("ghost", [])
        score = self.engine.get_activity_score("ghost", p)
        assert score == 0.0

    def test_combined_activities_score_additive(self) -> None:
        p = GovernanceParticipant(
            "multi",
            [
                GovernanceActivity(GovernanceActivityType.VOTE),
                GovernanceActivity(GovernanceActivityType.REVIEW),
            ],
        )
        score = self.engine.get_activity_score("multi", p)
        expected = (
            DEFAULT_ACTIVITY_TYPE_WEIGHTS[GovernanceActivityType.VOTE]
            + DEFAULT_ACTIVITY_TYPE_WEIGHTS[GovernanceActivityType.REVIEW]
        )
        assert score == pytest.approx(expected)

    def test_ledger_fallback_after_registration(self) -> None:
        p = _voter("carol")
        self.engine.get_activity_score("carol", p)  # registers in ledger
        # Now query without participant instance
        score = self.engine.get_activity_score("carol")
        assert score > 0.0


# ---------------------------------------------------------------------------
# distribute
# ---------------------------------------------------------------------------

class TestDistribute:
    def setup_method(self) -> None:
        self.engine = GovernanceRewardEngine()

    def test_single_participant_receives_all(self) -> None:
        result = self.engine.distribute(
            pool_amount=Decimal("100.00"),
            participants=[_voter("alice")],
        )
        total = sum(result.allocations.values()) + result.residual
        assert abs(total - Decimal("100.00")) < Decimal("0.001")
        assert result.allocations["alice"] > Decimal("0")

    def test_conservation_of_pool(self) -> None:
        participants = [_voter("a"), _proposer("b"), _voter("c")]
        pool = Decimal("500.00")
        result = self.engine.distribute(pool_amount=pool, participants=participants)
        distributed = sum(result.allocations.values()) + result.residual
        assert abs(distributed - pool) < Decimal("0.001")

    def test_proposer_earns_more_than_voter(self) -> None:
        participants = [_voter("voter"), _proposer("proposer")]
        result = self.engine.distribute(
            pool_amount=Decimal("100.00"),
            participants=participants,
        )
        assert result.allocations["proposer"] > result.allocations["voter"]

    def test_zero_pool_distributes_zero(self) -> None:
        result = self.engine.distribute(
            pool_amount=Decimal("0"),
            participants=[_voter("alice"), _voter("bob")],
        )
        for alloc in result.allocations.values():
            assert alloc == Decimal("0")

    def test_negative_pool_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            self.engine.distribute(
                pool_amount=Decimal("-1"),
                participants=[_voter("alice")],
            )

    def test_empty_participants_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.engine.distribute(pool_amount=Decimal("100"), participants=[])

    def test_epoch_propagated(self) -> None:
        result = self.engine.distribute(
            pool_amount=Decimal("50"),
            participants=[_voter("alice")],
            epoch="epoch-7",
        )
        assert result.epoch == "epoch-7"

    def test_activity_scores_in_result(self) -> None:
        result = self.engine.distribute(
            pool_amount=Decimal("100"),
            participants=[_voter("alice"), _proposer("bob")],
        )
        assert "alice" in result.activity_scores
        assert "bob" in result.activity_scores
        assert result.activity_scores["bob"] > result.activity_scores["alice"]

    def test_all_zero_activities_distribute_zero(self) -> None:
        participants = [
            GovernanceParticipant("a", []),
            GovernanceParticipant("b", []),
        ]
        result = self.engine.distribute(
            pool_amount=Decimal("100"),
            participants=participants,
        )
        for alloc in result.allocations.values():
            assert alloc == Decimal("0")


# ---------------------------------------------------------------------------
# calculate_rewards
# ---------------------------------------------------------------------------

class TestCalculateRewards:
    def setup_method(self) -> None:
        self.engine = GovernanceRewardEngine()

    def test_returns_dict_of_participant_ids(self) -> None:
        rewards = self.engine.calculate_rewards(
            participants=[_voter("alice"), _proposer("bob")],
            pool_amount=Decimal("100"),
        )
        assert set(rewards.keys()) == {"alice", "bob"}

    def test_rewards_sum_conserved(self) -> None:
        pool = Decimal("200.00")
        rewards = self.engine.calculate_rewards(
            participants=[_voter("x"), _proposer("y"), _voter("z")],
            pool_amount=pool,
        )
        total = sum(rewards.values())
        # Allow small rounding residual
        assert abs(total - pool) < Decimal("0.01")

    def test_higher_activity_higher_reward(self) -> None:
        rewards = self.engine.calculate_rewards(
            participants=[_voter("v"), _proposer("p")],
            pool_amount=Decimal("100"),
        )
        assert rewards["p"] > rewards["v"]


# ---------------------------------------------------------------------------
# record_activity & ledger
# ---------------------------------------------------------------------------

class TestRecordActivity:
    def setup_method(self) -> None:
        self.engine = GovernanceRewardEngine()

    def test_record_increments_score(self) -> None:
        self.engine.record_activity(
            "alice", GovernanceActivity(GovernanceActivityType.VOTE)
        )
        score = self.engine.get_activity_score("alice")
        assert score > 0.0

    def test_multiple_records_accumulate(self) -> None:
        for _ in range(3):
            self.engine.record_activity(
                "alice", GovernanceActivity(GovernanceActivityType.VOTE)
            )
        score = self.engine.get_activity_score("alice")
        single = DEFAULT_ACTIVITY_TYPE_WEIGHTS[GovernanceActivityType.VOTE]
        assert score == pytest.approx(3 * single)

    def test_activity_type_weight_accessor(self) -> None:
        w = self.engine.activity_type_weight(GovernanceActivityType.PROPOSAL)
        assert w == DEFAULT_ACTIVITY_TYPE_WEIGHTS[GovernanceActivityType.PROPOSAL]
