#!/usr/bin/env python3
"""Tests for fee_proof_engine (Phase 5).

pytest-compatible, also runnable as plain unittest.
"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fee_proof_engine import (
    AllocationLine,
    BatchProof,
    FeeBoundary,
    FeeProof,
    FeeProofEngine,
    ProofStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lines(boundary: FeeBoundary = FeeBoundary.PEER) -> list:
    return [
        AllocationLine(
            recipient_id="did:ssid:developer",
            role="developer_reward",
            boundary=boundary,
            amount=Decimal("10.00"),
            ratio=Decimal("0.01"),
        ),
        AllocationLine(
            recipient_id="did:ssid:system_pool",
            role="system_pool",
            boundary=FeeBoundary.UTILITY,
            amount=Decimal("20.00"),
            ratio=Decimal("0.02"),
        ),
    ]


# ---------------------------------------------------------------------------
# AllocationLine tests
# ---------------------------------------------------------------------------

class TestAllocationLine(unittest.TestCase):

    def test_to_dict_all_strings(self) -> None:
        line = AllocationLine(
            recipient_id="did:ssid:x",
            role="dao_treasury",
            boundary=FeeBoundary.UTILITY,
            amount=Decimal("50.00"),
            ratio=Decimal("0.05"),
        )
        d = line.to_dict()
        self.assertEqual(d["recipient_id"], "did:ssid:x")
        self.assertEqual(d["role"], "dao_treasury")
        self.assertEqual(d["boundary"], "utility")
        self.assertEqual(d["amount"], "50.00")
        self.assertEqual(d["ratio"], "0.05")

    def test_frozen(self) -> None:
        line = AllocationLine(
            recipient_id="x", role="r",
            boundary=FeeBoundary.PEER,
            amount=Decimal("1"), ratio=Decimal("0.01"),
        )
        with self.assertRaises(Exception):
            line.role = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FeeProofEngine tests
# ---------------------------------------------------------------------------

class TestFeeProofEngine(unittest.TestCase):

    def setUp(self) -> None:
        self.engine = FeeProofEngine()

    def test_generate_proof_returns_fee_proof(self) -> None:
        proof = self.engine.generate_proof(
            gross_amount=Decimal("1000.00"),
            fee_boundary=FeeBoundary.PEER,
            allocations=_make_lines(),
        )
        self.assertIsInstance(proof, FeeProof)
        self.assertIsNotNone(proof.proof_id)
        self.assertIsNotNone(proof.proof_hash)
        self.assertEqual(proof.status, ProofStatus.PENDING)

    def test_generate_proof_deterministic_hash(self) -> None:
        """Same inputs except proof_id (uuid) — hashes must differ each call
        because proof_id is embedded.  But the hash function itself is
        deterministic given fixed inputs."""
        engine = FeeProofEngine()
        lines = _make_lines()
        p1 = engine.generate_proof(Decimal("100"), FeeBoundary.PEER, lines)
        p2 = engine.generate_proof(Decimal("100"), FeeBoundary.PEER, lines)
        # Different proof_ids → different hashes
        self.assertNotEqual(p1.proof_hash, p2.proof_hash)

    def test_negative_gross_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.generate_proof(
                gross_amount=Decimal("-1"),
                fee_boundary=FeeBoundary.PEER,
                allocations=[],
            )

    def test_verify_proof_valid(self) -> None:
        proof = self.engine.generate_proof(
            gross_amount=Decimal("1000.00"),
            fee_boundary=FeeBoundary.PEER,
            allocations=_make_lines(),
        )
        self.assertTrue(self.engine.verify_proof(proof))
        self.assertEqual(proof.status, ProofStatus.VERIFIED)

    def test_verify_proof_tampered_hash(self) -> None:
        proof = self.engine.generate_proof(
            gross_amount=Decimal("1000.00"),
            fee_boundary=FeeBoundary.PEER,
            allocations=_make_lines(),
        )
        # Tamper with the stored hash
        proof.proof_hash = "00" * 32  # type: ignore[misc]
        self.assertFalse(self.engine.verify_proof(proof))
        self.assertEqual(proof.status, ProofStatus.INVALID)

    def test_verify_proof_allocation_exceeds_gross(self) -> None:
        lines = [
            AllocationLine(
                recipient_id="x", role="r",
                boundary=FeeBoundary.UTILITY,
                amount=Decimal("999999.00"),
                ratio=Decimal("0.99"),
            )
        ]
        proof = self.engine.generate_proof(
            gross_amount=Decimal("1.00"),
            fee_boundary=FeeBoundary.PEER,
            allocations=lines,
        )
        # Recompute hash manually so hash is valid but allocation exceeds gross
        # We need to force the allocation_exceeds check:
        # The proof hash will be valid but total_allocated > gross_amount
        self.assertFalse(self.engine.verify_proof(proof))

    def test_verify_proof_by_id(self) -> None:
        proof = self.engine.generate_proof(
            gross_amount=Decimal("500"),
            fee_boundary=FeeBoundary.REWARD,
            allocations=_make_lines(FeeBoundary.REWARD),
        )
        self.assertTrue(self.engine.verify_proof_by_id(proof.proof_id))

    def test_verify_proof_by_id_not_found(self) -> None:
        self.assertFalse(self.engine.verify_proof_by_id("nonexistent_id"))

    def test_get_proof_returns_registered(self) -> None:
        proof = self.engine.generate_proof(
            gross_amount=Decimal("100"),
            fee_boundary=FeeBoundary.PROOF,
            allocations=[],
        )
        fetched = self.engine.get_proof(proof.proof_id)
        self.assertIs(fetched, proof)

    def test_get_proof_not_found(self) -> None:
        self.assertIsNone(self.engine.get_proof("nope"))

    def test_all_proofs_returns_all(self) -> None:
        self.assertEqual(len(self.engine.all_proofs()), 0)
        self.engine.generate_proof(Decimal("1"), FeeBoundary.PEER, [])
        self.engine.generate_proof(Decimal("2"), FeeBoundary.UTILITY, [])
        self.assertEqual(len(self.engine.all_proofs()), 2)

    def test_parent_proof_chain(self) -> None:
        p1 = self.engine.generate_proof(
            gross_amount=Decimal("100"),
            fee_boundary=FeeBoundary.PEER,
            allocations=[],
        )
        p2 = self.engine.generate_proof(
            gross_amount=Decimal("50"),
            fee_boundary=FeeBoundary.PEER,
            allocations=[],
            parent_proof_id=p1.proof_id,
        )
        self.assertEqual(p2.parent_proof_id, p1.proof_id)
        self.assertTrue(self.engine.verify_proof(p2))

    def test_proof_to_audit_dict(self) -> None:
        proof = self.engine.generate_proof(
            gross_amount=Decimal("200"),
            fee_boundary=FeeBoundary.UTILITY,
            allocations=_make_lines(),
        )
        d = proof.to_audit_dict()
        self.assertEqual(d["gross_amount"], "200")
        self.assertEqual(d["fee_boundary"], "utility")
        self.assertEqual(d["status"], "pending")
        self.assertIn("proof_hash", d)
        self.assertEqual(d["allocation_count"], 2)

    def test_total_allocated_and_remainder(self) -> None:
        lines = [
            AllocationLine("x", "r1", FeeBoundary.PEER, Decimal("10"), Decimal("0.01")),
            AllocationLine("y", "r2", FeeBoundary.UTILITY, Decimal("20"), Decimal("0.02")),
        ]
        proof = self.engine.generate_proof(
            gross_amount=Decimal("100"),
            fee_boundary=FeeBoundary.PEER,
            allocations=lines,
        )
        self.assertEqual(proof.total_allocated(), Decimal("30"))
        self.assertEqual(proof.remainder(), Decimal("70"))

    # Batch proof tests

    def test_generate_batch_proof(self) -> None:
        p1 = self.engine.generate_proof(Decimal("100"), FeeBoundary.PEER, [])
        p2 = self.engine.generate_proof(Decimal("200"), FeeBoundary.UTILITY, [])
        batch = self.engine.generate_batch_proof([p1.proof_id, p2.proof_id])
        self.assertIsInstance(batch, BatchProof)
        self.assertEqual(batch.total_gross, Decimal("300"))
        self.assertEqual(batch.status, ProofStatus.VERIFIED)
        self.assertIsNotNone(batch.merkle_root)
        # Individual proofs should now have merkle_root set
        self.assertEqual(p1.merkle_root, batch.merkle_root)

    def test_batch_proof_missing_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.generate_batch_proof(["nonexistent_id"])

    def test_batch_merkle_root_is_deterministic(self) -> None:
        """Two batches with same proof set must produce same merkle root."""
        p1 = self.engine.generate_proof(Decimal("10"), FeeBoundary.PEER, [])
        p2 = self.engine.generate_proof(Decimal("20"), FeeBoundary.PROOF, [])
        b1 = self.engine.generate_batch_proof([p1.proof_id, p2.proof_id])
        b2 = self.engine.generate_batch_proof([p1.proof_id, p2.proof_id])
        self.assertEqual(b1.merkle_root, b2.merkle_root)

    def test_all_fee_boundaries(self) -> None:
        for boundary in FeeBoundary:
            proof = self.engine.generate_proof(
                Decimal("50"), boundary, []
            )
            self.assertTrue(self.engine.verify_proof(proof))


if __name__ == "__main__":
    unittest.main()
