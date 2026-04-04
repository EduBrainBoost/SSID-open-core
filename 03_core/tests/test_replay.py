"""P3.3 Replay tests — serialize, deserialize, replay, verify identical output.

Tests that SSID distributions produce stable, replayable results:
- Replay: inputs → result → serialize inputs → re-run with same inputs → same result
- Canonical hash: each result has a deterministic hash that changes when values change
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fee_distribution_engine import FeeDistributionEngine, FeeParticipant, ParticipantRole
from governance_reward_engine import (
    GovernanceActivity,
    GovernanceActivityType,
    GovernanceParticipant,
    GovernanceRewardEngine,
)
from subscription_revenue_distributor import RevenueParticipant, SubscriptionRevenueDistributor, SubscriptionTier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def canonical_hash(allocations: dict) -> str:
    """Deterministic SHA-256 of sorted allocation dict."""
    normalized = {k: str(v) for k, v in sorted(allocations.items())}
    return hashlib.sha256(json.dumps(normalized).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fee Distribution Replay Tests
# ---------------------------------------------------------------------------


class TestFeeDistributionReplay:
    """Replay and canonical-hash tests for FeeDistributionEngine."""

    def _make_participants(self):
        return [
            FeeParticipant("validator_1", ParticipantRole.VALIDATOR, 0.9),
            FeeParticipant("provider_1", ParticipantRole.PROVIDER, 0.8),
            FeeParticipant("consumer_1", ParticipantRole.CONSUMER, 0.5),
            FeeParticipant("governance_1", ParticipantRole.GOVERNANCE, 0.7),
        ]

    def test_replay_identical_inputs_same_allocations(self):
        """Two runs with identical inputs produce identical allocations."""
        engine = FeeDistributionEngine()
        participants = self._make_participants()
        fee = Decimal("100.00")

        result1 = engine.distribute(total_fee=fee, participants=participants)
        result2 = engine.distribute(total_fee=fee, participants=participants)

        assert result1.allocations == result2.allocations

    def test_canonical_hash_stable(self):
        """The canonical hash of allocations is stable across two runs."""
        engine = FeeDistributionEngine()
        participants = self._make_participants()
        fee = Decimal("100.00")

        result1 = engine.distribute(total_fee=fee, participants=participants)
        result2 = engine.distribute(total_fee=fee, participants=participants)

        hash1 = canonical_hash(result1.allocations)
        hash2 = canonical_hash(result2.allocations)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length

    def test_canonical_hash_changes_on_different_fee(self):
        """Hash with fee=100 differs from hash with fee=200."""
        engine = FeeDistributionEngine()
        participants = self._make_participants()

        result_100 = engine.distribute(total_fee=Decimal("100.00"), participants=participants)
        result_200 = engine.distribute(total_fee=Decimal("200.00"), participants=participants)

        hash_100 = canonical_hash(result_100.allocations)
        hash_200 = canonical_hash(result_200.allocations)

        assert hash_100 != hash_200

    def test_serialized_inputs_round_trip(self):
        """Serialize inputs to JSON, deserialize, rebuild participants, re-run → same result."""
        engine = FeeDistributionEngine()
        participants = self._make_participants()
        fee = Decimal("100.00")

        # Run original
        result_original = engine.distribute(total_fee=fee, participants=participants)

        # Serialize inputs
        inputs = {
            "fee": str(fee),
            "participants": [
                {
                    "participant_id": p.participant_id,
                    "role": p.role.value,
                    "contribution_score": p.contribution_score,
                }
                for p in participants
            ],
        }
        serialized = json.dumps(inputs)

        # Deserialize and rebuild
        deserialized = json.loads(serialized)
        rebuilt_participants = [
            FeeParticipant(
                participant_id=p["participant_id"],
                role=ParticipantRole(p["role"]),
                contribution_score=p["contribution_score"],
            )
            for p in deserialized["participants"]
        ]
        rebuilt_fee = Decimal(deserialized["fee"])

        result_replay = engine.distribute(total_fee=rebuilt_fee, participants=rebuilt_participants)

        assert result_original.allocations == result_replay.allocations


# ---------------------------------------------------------------------------
# Subscription Revenue Replay Tests
# ---------------------------------------------------------------------------


class TestSubscriptionReplay:
    """Replay and canonical-hash tests for SubscriptionRevenueDistributor."""

    def _make_participants(self):
        return [
            RevenueParticipant("provider_a", service_units=60, tier=SubscriptionTier.STARTER),
            RevenueParticipant("provider_b", service_units=30, tier=SubscriptionTier.STARTER),
            RevenueParticipant("provider_c", service_units=10, tier=SubscriptionTier.STARTER),
        ]

    def test_replay_same_revenue_same_allocations(self):
        """Two runs with same participants and STARTER tier produce identical allocations."""
        distributor = SubscriptionRevenueDistributor()
        participants = self._make_participants()
        gross_revenue = Decimal("1000.00")

        result1 = distributor.distribute(
            gross_revenue=gross_revenue,
            participants=participants,
            tier=SubscriptionTier.STARTER,
        )
        result2 = distributor.distribute(
            gross_revenue=gross_revenue,
            participants=participants,
            tier=SubscriptionTier.STARTER,
        )

        assert result1.allocations == result2.allocations

    def test_canonical_hash_stable(self):
        """Canonical hash of subscription allocations is stable across two identical runs."""
        distributor = SubscriptionRevenueDistributor()
        participants = self._make_participants()
        gross_revenue = Decimal("1000.00")

        result1 = distributor.distribute(
            gross_revenue=gross_revenue,
            participants=participants,
            tier=SubscriptionTier.STARTER,
        )
        result2 = distributor.distribute(
            gross_revenue=gross_revenue,
            participants=participants,
            tier=SubscriptionTier.STARTER,
        )

        assert canonical_hash(result1.allocations) == canonical_hash(result2.allocations)

    def test_canonical_hash_changes_on_tier_change(self):
        """STARTER vs ENTERPRISE tier produces different allocations (different retention rate)."""
        distributor = SubscriptionRevenueDistributor()
        participants = self._make_participants()
        gross_revenue = Decimal("1000.00")

        result_starter = distributor.distribute(
            gross_revenue=gross_revenue,
            participants=participants,
            tier=SubscriptionTier.STARTER,
        )
        result_enterprise = distributor.distribute(
            gross_revenue=gross_revenue,
            participants=participants,
            tier=SubscriptionTier.ENTERPRISE,
        )

        # STARTER retains 30%, ENTERPRISE retains 10% → different distributable → different allocations
        hash_starter = canonical_hash(result_starter.allocations)
        hash_enterprise = canonical_hash(result_enterprise.allocations)

        assert hash_starter != hash_enterprise


# ---------------------------------------------------------------------------
# Governance Reward Replay Tests
# ---------------------------------------------------------------------------


class TestGovernanceReplay:
    """Replay and canonical-hash tests for GovernanceRewardEngine."""

    def _make_participants(self):
        return [
            GovernanceParticipant(
                participant_id="alice",
                activities=[
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                    GovernanceActivity(GovernanceActivityType.PROPOSAL, weight=2.0),
                ],
            ),
            GovernanceParticipant(
                participant_id="bob",
                activities=[
                    GovernanceActivity(GovernanceActivityType.VOTE, weight=1.0),
                    GovernanceActivity(GovernanceActivityType.REVIEW, weight=1.5),
                ],
            ),
            GovernanceParticipant(
                participant_id="carol",
                activities=[
                    GovernanceActivity(GovernanceActivityType.DELEGATION, weight=1.0),
                ],
            ),
        ]

    def test_replay_same_governance_same_rewards(self):
        """Two runs with same participants and pool produce identical allocations."""
        engine = GovernanceRewardEngine()
        participants = self._make_participants()
        pool = Decimal("500.00")

        result1 = engine.distribute(pool_amount=pool, participants=participants, epoch="2026-Q1")
        # Re-create engine to ensure no ledger state bleeds — uses fresh participants each time
        engine2 = GovernanceRewardEngine()
        result2 = engine2.distribute(pool_amount=pool, participants=self._make_participants(), epoch="2026-Q1")

        assert result1.allocations == result2.allocations

    def test_canonical_hash_stable(self):
        """Canonical hash of governance allocations is stable across two identical runs."""
        engine = GovernanceRewardEngine()
        participants = self._make_participants()
        pool = Decimal("500.00")

        result1 = engine.distribute(pool_amount=pool, participants=participants)
        engine2 = GovernanceRewardEngine()
        result2 = engine2.distribute(pool_amount=pool, participants=self._make_participants())

        assert canonical_hash(result1.allocations) == canonical_hash(result2.allocations)

    def test_serialized_epoch_preserved(self):
        """Epoch passed to distribute() is preserved in the result."""
        engine = GovernanceRewardEngine()
        participants = self._make_participants()
        pool = Decimal("500.00")
        epoch = "2026-Q1"

        result = engine.distribute(pool_amount=pool, participants=participants, epoch=epoch)

        # GovernanceRewardResult has an epoch field — verify it is preserved
        assert result.epoch == epoch
        # Also verify allocations are non-empty and stable
        assert len(result.allocations) == 3
        assert all(v >= Decimal("0") for v in result.allocations.values())
