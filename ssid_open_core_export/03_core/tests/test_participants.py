#!/usr/bin/env python3
"""Tests for FeeParticipant and RevenueParticipant (Phase 5).

pytest-compatible, also runnable as plain unittest.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from participants import (
    FeeCategory,
    FeeParticipant,
    ParticipantRegistry,
    ParticipantStatus,
    RevenueCategory,
    RevenueParticipant,
)

# ---------------------------------------------------------------------------
# FeeParticipant tests
# ---------------------------------------------------------------------------


class TestFeeParticipant(unittest.TestCase):
    def _make_fee_participant(self, **kwargs) -> FeeParticipant:
        defaults = dict(
            participant_id="fp-001",
            display_name="Validator Alpha",
            fee_categories=[FeeCategory.PEER, FeeCategory.PROOF],
            reliability_score=0.9,
        )
        defaults.update(kwargs)
        return FeeParticipant(**defaults)

    def test_creation_defaults(self) -> None:
        p = self._make_fee_participant()
        self.assertEqual(p.participant_id, "fp-001")
        self.assertEqual(p.status, ParticipantStatus.ACTIVE)
        self.assertIsNone(p.address)
        self.assertEqual(p.metadata, {})

    def test_is_eligible_for_covered_category(self) -> None:
        p = self._make_fee_participant()
        self.assertTrue(p.is_eligible_for(FeeCategory.PEER))
        self.assertTrue(p.is_eligible_for(FeeCategory.PROOF))

    def test_is_not_eligible_for_uncovered_category(self) -> None:
        p = self._make_fee_participant()
        self.assertFalse(p.is_eligible_for(FeeCategory.UTILITY))
        self.assertFalse(p.is_eligible_for(FeeCategory.REWARD))

    def test_is_active(self) -> None:
        p = self._make_fee_participant()
        self.assertTrue(p.is_active())
        p2 = self._make_fee_participant(status=ParticipantStatus.SUSPENDED)
        self.assertFalse(p2.is_active())

    def test_reliability_score_validation(self) -> None:
        with self.assertRaises(ValueError):
            self._make_fee_participant(reliability_score=1.1)
        with self.assertRaises(ValueError):
            self._make_fee_participant(reliability_score=-0.01)

    def test_empty_participant_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._make_fee_participant(participant_id="")

    def test_empty_display_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._make_fee_participant(display_name="")

    def test_empty_fee_categories_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._make_fee_participant(fee_categories=[])

    def test_to_audit_dict_no_address(self) -> None:
        p = self._make_fee_participant(address="did:ssid:validator:abc123")
        d = p.to_audit_dict()
        # Address must NOT appear in audit dict
        self.assertNotIn("address", d)
        self.assertEqual(d["participant_id"], "fp-001")
        self.assertIn("peer", d["fee_categories"])

    def test_identity_hash_is_deterministic(self) -> None:
        p = self._make_fee_participant()
        self.assertEqual(p.identity_hash(), p.identity_hash())

    def test_identity_hash_differs_for_different_ids(self) -> None:
        p1 = self._make_fee_participant(participant_id="fp-001")
        p2 = self._make_fee_participant(participant_id="fp-002")
        self.assertNotEqual(p1.identity_hash(), p2.identity_hash())

    def test_all_fee_categories(self) -> None:
        for cat in FeeCategory:
            p = FeeParticipant(
                participant_id=f"fp-{cat.value}",
                display_name=cat.value,
                fee_categories=[cat],
            )
            self.assertTrue(p.is_eligible_for(cat))


# ---------------------------------------------------------------------------
# RevenueParticipant tests
# ---------------------------------------------------------------------------


class TestRevenueParticipant(unittest.TestCase):
    def _make_revenue_participant(self, **kwargs) -> RevenueParticipant:
        defaults = dict(
            participant_id="rp-001",
            display_name="Core Developer Pool",
            revenue_categories=[RevenueCategory.DEVELOPER_CORE],
            allocation_ratio=1.0,
            vesting_days=90,
        )
        defaults.update(kwargs)
        return RevenueParticipant(**defaults)

    def test_creation_defaults(self) -> None:
        p = self._make_revenue_participant()
        self.assertEqual(p.participant_id, "rp-001")
        self.assertEqual(p.status, ParticipantStatus.ACTIVE)
        self.assertEqual(p.metadata, {})

    def test_is_eligible_for_covered_category(self) -> None:
        p = self._make_revenue_participant()
        self.assertTrue(p.is_eligible_for(RevenueCategory.DEVELOPER_CORE))

    def test_is_not_eligible_for_uncovered_category(self) -> None:
        p = self._make_revenue_participant()
        self.assertFalse(p.is_eligible_for(RevenueCategory.DAO_TREASURY))

    def test_has_vesting(self) -> None:
        p = self._make_revenue_participant(vesting_days=90)
        self.assertTrue(p.has_vesting())
        p2 = self._make_revenue_participant(vesting_days=0)
        self.assertFalse(p2.has_vesting())

    def test_allocation_ratio_validation(self) -> None:
        with self.assertRaises(ValueError):
            self._make_revenue_participant(allocation_ratio=1.1)
        with self.assertRaises(ValueError):
            self._make_revenue_participant(allocation_ratio=-0.01)

    def test_negative_vesting_days_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._make_revenue_participant(vesting_days=-1)

    def test_empty_revenue_categories_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._make_revenue_participant(revenue_categories=[])

    def test_to_audit_dict_structure(self) -> None:
        p = self._make_revenue_participant()
        d = p.to_audit_dict()
        self.assertEqual(d["participant_id"], "rp-001")
        self.assertIn("developer_core", d["revenue_categories"])
        self.assertEqual(d["vesting_days"], 90)

    def test_identity_hash_is_deterministic(self) -> None:
        p = self._make_revenue_participant()
        self.assertEqual(p.identity_hash(), p.identity_hash())

    def test_identity_hash_changes_with_vesting(self) -> None:
        p1 = self._make_revenue_participant(vesting_days=0)
        p2 = self._make_revenue_participant(vesting_days=90)
        self.assertNotEqual(p1.identity_hash(), p2.identity_hash())

    def test_all_revenue_categories(self) -> None:
        for cat in RevenueCategory:
            p = RevenueParticipant(
                participant_id=f"rp-{cat.value}",
                display_name=cat.value,
                revenue_categories=[cat],
            )
            self.assertTrue(p.is_eligible_for(cat))

    def test_multi_category_participant(self) -> None:
        p = RevenueParticipant(
            participant_id="rp-multi",
            display_name="Multi-pool",
            revenue_categories=[
                RevenueCategory.SYSTEM_OPERATIONAL,
                RevenueCategory.DAO_TREASURY,
            ],
        )
        self.assertTrue(p.is_eligible_for(RevenueCategory.SYSTEM_OPERATIONAL))
        self.assertTrue(p.is_eligible_for(RevenueCategory.DAO_TREASURY))
        self.assertFalse(p.is_eligible_for(RevenueCategory.DEVELOPER_CORE))


# ---------------------------------------------------------------------------
# ParticipantRegistry tests
# ---------------------------------------------------------------------------


class TestParticipantRegistry(unittest.TestCase):
    def _make_fee(self, pid: str = "fp-001") -> FeeParticipant:
        return FeeParticipant(
            participant_id=pid,
            display_name=f"Node {pid}",
            fee_categories=[FeeCategory.PEER],
        )

    def _make_revenue(self, pid: str = "rp-001") -> RevenueParticipant:
        return RevenueParticipant(
            participant_id=pid,
            display_name=f"Pool {pid}",
            revenue_categories=[RevenueCategory.DAO_TREASURY],
        )

    def test_register_and_get_fee_participant(self) -> None:
        reg = ParticipantRegistry()
        p = self._make_fee()
        reg.register_fee_participant(p)
        self.assertIs(reg.get_fee_participant("fp-001"), p)

    def test_duplicate_fee_participant_raises(self) -> None:
        reg = ParticipantRegistry()
        reg.register_fee_participant(self._make_fee())
        with self.assertRaises(ValueError):
            reg.register_fee_participant(self._make_fee())

    def test_get_missing_fee_participant_returns_none(self) -> None:
        reg = ParticipantRegistry()
        self.assertIsNone(reg.get_fee_participant("nonexistent"))

    def test_active_fee_participants_filter_by_category(self) -> None:
        reg = ParticipantRegistry()
        p1 = FeeParticipant("fp-1", "A", [FeeCategory.PEER])
        p2 = FeeParticipant("fp-2", "B", [FeeCategory.UTILITY])
        p3 = FeeParticipant("fp-3", "C", [FeeCategory.PEER], status=ParticipantStatus.SUSPENDED)
        for p in (p1, p2, p3):
            reg.register_fee_participant(p)

        active_peer = reg.active_fee_participants(FeeCategory.PEER)
        self.assertEqual(len(active_peer), 1)
        self.assertEqual(active_peer[0].participant_id, "fp-1")

    def test_register_and_get_revenue_participant(self) -> None:
        reg = ParticipantRegistry()
        p = self._make_revenue()
        reg.register_revenue_participant(p)
        self.assertIs(reg.get_revenue_participant("rp-001"), p)

    def test_duplicate_revenue_participant_raises(self) -> None:
        reg = ParticipantRegistry()
        reg.register_revenue_participant(self._make_revenue())
        with self.assertRaises(ValueError):
            reg.register_revenue_participant(self._make_revenue())

    def test_active_revenue_participants_filter_by_category(self) -> None:
        reg = ParticipantRegistry()
        p1 = RevenueParticipant("rp-1", "A", [RevenueCategory.DAO_TREASURY])
        p2 = RevenueParticipant("rp-2", "B", [RevenueCategory.DEVELOPER_CORE])
        p3 = RevenueParticipant(
            "rp-3",
            "C",
            [RevenueCategory.DAO_TREASURY],
            status=ParticipantStatus.RETIRED,
        )
        for p in (p1, p2, p3):
            reg.register_revenue_participant(p)

        dao = reg.active_revenue_participants(RevenueCategory.DAO_TREASURY)
        self.assertEqual(len(dao), 1)
        self.assertEqual(dao[0].participant_id, "rp-1")


if __name__ == "__main__":
    unittest.main()
