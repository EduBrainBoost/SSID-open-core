"""fee_proof_engine — Fee allocation proof generation and verification.

Generates cryptographic proofs of fee allocation decisions and verifies
them for audit traceability.  All proofs are SHA-256 hash manifests over
canonical, deterministic JSON — no PII, no custody, no on-chain execution.

Referenced in SoT:
  SSID_structure_gebuehren_abo_modelle.md §6:
      "Proof-of-Allocation über Merkle-Hash jeder Ausschüttung
       (nach 02_audit_logging/fee_proof_engine.py)"

  SSID_structure_gebuehren_abo_modelle_ROOTS_16_21_ADDENDUM.md:
      Fee Cascade Analysis — cross-root proof anchoring

SoT v4.1.0 | ROOT-24-LOCK | Module: 03_core
Evidence strategy: hash_manifest_only
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class ProofStatus(str, Enum):
    """Status of a fee allocation proof."""
    PENDING = "pending"
    VERIFIED = "verified"
    INVALID = "invalid"


class FeeBoundary(str, Enum):
    """Fee boundary categories from the SSID SoT.

    Derived from SSID_structure_gebuehren_abo_modelle.md 7-Säulen-Verteilung:
    - PEER:    Peer transaction 3% fee split
    - PROOF:   Proof-of-Allocation hash verification costs
    - UTILITY: System operational (Legal, Audit, Tech, DAO, Community,
               Liquidity, Marketing)
    - REWARD:  Developer reward (1% developer share)
    """
    PEER = "peer"
    PROOF = "proof"
    UTILITY = "utility"
    REWARD = "reward"


@dataclass(frozen=True)
class AllocationLine:
    """One line in a fee allocation proof.

    Attributes:
        recipient_id: Anonymised recipient identifier (DID or hash).
        role: Descriptive role label (e.g. 'developer_reward', 'dao_treasury').
        boundary: Fee boundary category.
        amount: Allocated amount as Decimal.
        ratio: Fraction of the total gross fee (0–1).
    """
    recipient_id: str
    role: str
    boundary: FeeBoundary
    amount: Decimal
    ratio: Decimal

    def to_dict(self) -> Dict[str, str]:
        """Canonical dict for hashing — all values as str."""
        return {
            "recipient_id": self.recipient_id,
            "role": self.role,
            "boundary": self.boundary.value,
            "amount": str(self.amount),
            "ratio": str(self.ratio),
        }


@dataclass
class FeeProof:
    """A generated fee allocation proof.

    Attributes:
        proof_id: UUID4 hex identifier.
        timestamp: ISO-8601 UTC timestamp at generation time.
        gross_amount: Total gross fee amount the proof covers.
        fee_boundary: Primary fee boundary category for this proof.
        allocations: Ordered list of per-recipient allocation lines.
        proof_hash: SHA-256 of the canonical proof JSON payload.
        status: Verification status of this proof.
        parent_proof_id: Optional id of a prior proof in a proof chain.
        merkle_root: Optional Merkle root if this proof is part of a batch.
    """
    proof_id: str
    timestamp: str
    gross_amount: Decimal
    fee_boundary: FeeBoundary
    allocations: List[AllocationLine]
    proof_hash: str
    status: ProofStatus = ProofStatus.PENDING
    parent_proof_id: Optional[str] = None
    merkle_root: Optional[str] = None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def total_allocated(self) -> Decimal:
        """Return sum of all allocation amounts."""
        return sum(a.amount for a in self.allocations)

    def remainder(self) -> Decimal:
        """Return unallocated gross amount (rounding residual)."""
        return self.gross_amount - self.total_allocated()

    def to_audit_dict(self) -> Dict[str, object]:
        """Return PII-free dict for audit logging."""
        return {
            "proof_id": self.proof_id,
            "timestamp": self.timestamp,
            "gross_amount": str(self.gross_amount),
            "fee_boundary": self.fee_boundary.value,
            "proof_hash": self.proof_hash,
            "status": self.status.value,
            "allocation_count": len(self.allocations),
            "total_allocated": str(self.total_allocated()),
            "remainder": str(self.remainder()),
            "parent_proof_id": self.parent_proof_id,
            "merkle_root": self.merkle_root,
        }


@dataclass
class BatchProof:
    """Proof for a batch of individual FeeProofs (Merkle-style aggregation).

    Attributes:
        batch_id: UUID4 hex identifier.
        timestamp: ISO-8601 UTC timestamp.
        proof_ids: Ordered list of proof_ids included in this batch.
        merkle_root: SHA-256 Merkle root of sorted proof hashes.
        total_gross: Sum of all gross amounts in the batch.
        status: Verification status.
    """
    batch_id: str
    timestamp: str
    proof_ids: List[str]
    merkle_root: str
    total_gross: Decimal
    status: ProofStatus = ProofStatus.PENDING


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FeeProofEngine:
    """Generates and verifies cryptographic proofs of fee allocations.

    Design principles:
    - Non-custodial: no wallets, balances, or payment execution.
    - Hash-only evidence: SHA-256 over canonical JSON; no PII stored.
    - Deterministic: identical inputs always produce the same proof hash.
    - Audit-traceable: every proof stored in an internal ledger.

    Usage::

        engine = FeeProofEngine()

        lines = [
            AllocationLine(
                recipient_id="did:ssid:developer",
                role="developer_reward",
                boundary=FeeBoundary.REWARD,
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
        proof = engine.generate_proof(
            gross_amount=Decimal("1000.00"),
            fee_boundary=FeeBoundary.PEER,
            allocations=lines,
        )
        assert engine.verify_proof(proof)
    """

    def __init__(self) -> None:
        # Ledger: proof_id -> FeeProof
        self._ledger: Dict[str, FeeProof] = {}
        # Batch ledger: batch_id -> BatchProof
        self._batch_ledger: Dict[str, BatchProof] = {}

    # ------------------------------------------------------------------
    # Proof generation
    # ------------------------------------------------------------------

    def generate_proof(
        self,
        gross_amount: Decimal,
        fee_boundary: FeeBoundary,
        allocations: Sequence[AllocationLine],
        parent_proof_id: Optional[str] = None,
    ) -> FeeProof:
        """Generate a new fee allocation proof.

        Args:
            gross_amount: Total gross fee amount this proof covers.
            fee_boundary: Primary fee boundary category.
            allocations: Ordered sequence of per-recipient allocation lines.
            parent_proof_id: Optional parent proof id for chaining.

        Returns:
            A ``FeeProof`` with a deterministic SHA-256 ``proof_hash``.

        Raises:
            ValueError: If gross_amount is negative.
        """
        if gross_amount < Decimal("0"):
            raise ValueError("gross_amount must not be negative")

        proof_id = uuid.uuid4().hex[:16]
        timestamp = datetime.now(timezone.utc).isoformat()

        proof_hash = self._compute_proof_hash(
            proof_id=proof_id,
            timestamp=timestamp,
            gross_amount=gross_amount,
            fee_boundary=fee_boundary,
            allocations=list(allocations),
            parent_proof_id=parent_proof_id,
        )

        proof = FeeProof(
            proof_id=proof_id,
            timestamp=timestamp,
            gross_amount=gross_amount,
            fee_boundary=fee_boundary,
            allocations=list(allocations),
            proof_hash=proof_hash,
            status=ProofStatus.PENDING,
            parent_proof_id=parent_proof_id,
        )
        self._ledger[proof_id] = proof
        return proof

    # ------------------------------------------------------------------
    # Proof verification
    # ------------------------------------------------------------------

    def verify_proof(self, proof: FeeProof) -> bool:
        """Verify the integrity of *proof* by recomputing its hash.

        Also checks that ``total_allocated <= gross_amount``.

        Args:
            proof: The proof to verify.

        Returns:
            True if the proof hash is valid and allocations are internally
            consistent; False otherwise.
        """
        expected = self._compute_proof_hash(
            proof_id=proof.proof_id,
            timestamp=proof.timestamp,
            gross_amount=proof.gross_amount,
            fee_boundary=proof.fee_boundary,
            allocations=proof.allocations,
            parent_proof_id=proof.parent_proof_id,
        )
        hash_valid = expected == proof.proof_hash
        allocation_valid = proof.total_allocated() <= proof.gross_amount

        if hash_valid and allocation_valid:
            proof.status = ProofStatus.VERIFIED
        else:
            proof.status = ProofStatus.INVALID

        # Update ledger copy if registered
        if proof.proof_id in self._ledger:
            self._ledger[proof.proof_id] = proof

        return hash_valid and allocation_valid

    def verify_proof_by_id(self, proof_id: str) -> bool:
        """Verify a ledgered proof by its id.

        Args:
            proof_id: Id of the proof to look up and verify.

        Returns:
            True if valid; False if invalid or not found.
        """
        proof = self._ledger.get(proof_id)
        if proof is None:
            return False
        return self.verify_proof(proof)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def generate_batch_proof(
        self, proof_ids: Sequence[str]
    ) -> BatchProof:
        """Generate a Merkle-style batch proof over a set of FeeProofs.

        The Merkle root is the SHA-256 of the space-joined sorted proof
        hashes of all included proofs.

        Args:
            proof_ids: Ids of registered proofs to include.

        Returns:
            A ``BatchProof`` with a Merkle root.

        Raises:
            ValueError: If any proof_id is not found in the ledger.
        """
        missing = [pid for pid in proof_ids if pid not in self._ledger]
        if missing:
            raise ValueError(
                f"Proof IDs not found in ledger: {', '.join(missing)}"
            )

        proofs = [self._ledger[pid] for pid in proof_ids]
        sorted_hashes = sorted(p.proof_hash for p in proofs)
        merkle_root = hashlib.sha256(
            " ".join(sorted_hashes).encode("utf-8")
        ).hexdigest()

        total_gross = sum(p.gross_amount for p in proofs)
        batch_id = uuid.uuid4().hex[:16]
        timestamp = datetime.now(timezone.utc).isoformat()

        # Annotate individual proofs with the batch merkle_root
        for p in proofs:
            p.merkle_root = merkle_root

        batch = BatchProof(
            batch_id=batch_id,
            timestamp=timestamp,
            proof_ids=list(proof_ids),
            merkle_root=merkle_root,
            total_gross=total_gross,
            status=ProofStatus.VERIFIED,
        )
        self._batch_ledger[batch_id] = batch
        return batch

    # ------------------------------------------------------------------
    # Ledger access
    # ------------------------------------------------------------------

    def get_proof(self, proof_id: str) -> Optional[FeeProof]:
        """Return a FeeProof by id, or None."""
        return self._ledger.get(proof_id)

    def get_batch_proof(self, batch_id: str) -> Optional[BatchProof]:
        """Return a BatchProof by id, or None."""
        return self._batch_ledger.get(batch_id)

    def all_proofs(self) -> List[FeeProof]:
        """Return a copy of all registered FeeProofs."""
        return list(self._ledger.values())

    def all_batch_proofs(self) -> List[BatchProof]:
        """Return a copy of all registered BatchProofs."""
        return list(self._batch_ledger.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_proof_hash(
        proof_id: str,
        timestamp: str,
        gross_amount: Decimal,
        fee_boundary: FeeBoundary,
        allocations: List[AllocationLine],
        parent_proof_id: Optional[str],
    ) -> str:
        """Compute deterministic SHA-256 proof hash."""
        payload: Dict[str, object] = {
            "proof_id": proof_id,
            "timestamp": timestamp,
            "gross_amount": str(gross_amount),
            "fee_boundary": fee_boundary.value,
            "allocations": [a.to_dict() for a in allocations],
            "parent_proof_id": parent_proof_id,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "FeeProofEngine",
    "FeeProof",
    "BatchProof",
    "AllocationLine",
    "FeeBoundary",
    "ProofStatus",
]
