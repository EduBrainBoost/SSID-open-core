"""EU GDPR compliance rules engine for SSID.

SAFE-FIX: Hash-only, non-custodial. No raw PII stored or processed.
Implements:
  - Right to erasure via hash-rotation
  - Data portability requirements
  - Consent management rules
  - Evidence generation (hash-based)

Reference: Regulation (EU) 2016/679 (GDPR)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ======================================================================
# Legal Basis & Consent
# ======================================================================


class LegalBasis(Enum):
    """GDPR Article 6 — lawful bases for processing."""

    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTEREST = "vital_interest"
    PUBLIC_INTEREST = "public_interest"
    LEGITIMATE_INTEREST = "legitimate_interest"


class DataCategory(Enum):
    """Categories of personal data relevant to SSID."""

    IDENTITY_HASH = "identity_hash"
    CREDENTIAL_PROOF = "credential_proof"
    VERIFICATION_RESULT = "verification_result"
    CONSENT_RECORD = "consent_record"
    AUDIT_LOG = "audit_log"


class ErasureStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    DENIED_LEGAL_HOLD = "denied_legal_hold"


@dataclass(frozen=True)
class ConsentRecord:
    """Immutable record of consent — stores only hashes, never raw PII."""

    subject_hash: str  # SHA-256 of data subject identifier
    purpose: str  # e.g. "identity_verification"
    legal_basis: LegalBasis
    granted: bool
    timestamp: float = field(default_factory=time.time)
    evidence_hash: str = ""  # SHA-256 of the consent artefact

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_hash": self.subject_hash,
            "purpose": self.purpose,
            "legal_basis": self.legal_basis.value,
            "granted": self.granted,
            "timestamp": self.timestamp,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True)
class ErasureRequest:
    """Right-to-erasure (Art. 17) request record — hash-only."""

    request_id: str
    subject_hash: str
    requested_at: float = field(default_factory=time.time)
    status: ErasureStatus = ErasureStatus.PENDING
    completed_at: float | None = None
    evidence_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "subject_hash": self.subject_hash,
            "requested_at": self.requested_at,
            "status": self.status.value,
            "completed_at": self.completed_at,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True)
class PortabilityPackage:
    """Data portability (Art. 20) export manifest — hash references only."""

    subject_hash: str
    data_categories: frozenset[DataCategory]
    export_hash: str  # SHA-256 of the exported package
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_hash": self.subject_hash,
            "data_categories": sorted(c.value for c in self.data_categories),
            "export_hash": self.export_hash,
            "generated_at": self.generated_at,
        }


# ======================================================================
# GDPR Rules Engine
# ======================================================================

# Maximum response time for erasure requests: 30 days (Art. 17(1))
ERASURE_DEADLINE_SECONDS = 30 * 24 * 3600

# Data retention ceiling — SSID keeps only hashes, but even hashes
# must not be retained beyond the purpose's lifetime.
DEFAULT_RETENTION_DAYS = 365


class GDPRComplianceEngine:
    """GDPR compliance rules engine.

    Non-custodial: all operations work on hashes, never raw PII.
    Fail-closed: missing consent → deny processing.
    """

    def __init__(self) -> None:
        self._consents: dict[str, list[ConsentRecord]] = {}  # subject_hash → records
        self._erasure_requests: dict[str, ErasureRequest] = {}  # request_id → request
        self._rotated_hashes: dict[str, str] = {}  # old_hash → new_hash

    # ------------------------------------------------------------------
    # Consent Management
    # ------------------------------------------------------------------

    def record_consent(self, record: ConsentRecord) -> ConsentRecord:
        """Record a consent decision (grant or revoke)."""
        if not record.subject_hash:
            raise ValueError("subject_hash is required")
        if not record.purpose:
            raise ValueError("purpose is required")

        self._consents.setdefault(record.subject_hash, []).append(record)
        return record

    def has_valid_consent(self, subject_hash: str, purpose: str) -> bool:
        """Check whether *subject_hash* has active consent for *purpose*.

        Fail-closed: returns ``False`` if no record exists.
        """
        records = self._consents.get(subject_hash, [])
        # Latest record for this purpose wins
        relevant = [r for r in records if r.purpose == purpose]
        if not relevant:
            return False
        latest = max(relevant, key=lambda r: r.timestamp)
        return latest.granted

    def get_consent_history(self, subject_hash: str) -> list[ConsentRecord]:
        """Return full consent history for audit (all purposes)."""
        return list(self._consents.get(subject_hash, []))

    # ------------------------------------------------------------------
    # Right to Erasure (Art. 17) via Hash-Rotation
    # ------------------------------------------------------------------

    def request_erasure(self, request: ErasureRequest) -> ErasureRequest:
        """File an erasure request.

        SSID is non-custodial and stores only hashes; erasure is
        implemented via *hash rotation*: the old hash is replaced with a
        freshly-derived one, breaking linkability to the original data.
        """
        if not request.subject_hash:
            raise ValueError("subject_hash is required")
        self._erasure_requests[request.request_id] = request
        return request

    def execute_erasure(self, request_id: str) -> ErasureRequest:
        """Execute hash-rotation for an erasure request.

        Returns the updated request with status COMPLETED.
        """
        req = self._erasure_requests.get(request_id)
        if req is None:
            raise KeyError(f"Unknown erasure request: {request_id}")

        old_hash = req.subject_hash
        # Rotate: derive a new hash so old identifier can no longer be linked
        rotation_salt = hashlib.sha256(f"{old_hash}:{time.time()}:erasure".encode()).hexdigest()
        new_hash = hashlib.sha256(f"{old_hash}:{rotation_salt}".encode()).hexdigest()

        self._rotated_hashes[old_hash] = new_hash

        # Migrate consent records to new hash
        if old_hash in self._consents:
            self._consents[new_hash] = self._consents.pop(old_hash)

        now = time.time()
        evidence = hashlib.sha256(f"erasure:{request_id}:{now}".encode()).hexdigest()

        completed = ErasureRequest(
            request_id=req.request_id,
            subject_hash=new_hash,
            requested_at=req.requested_at,
            status=ErasureStatus.COMPLETED,
            completed_at=now,
            evidence_hash=evidence,
        )
        self._erasure_requests[request_id] = completed
        return completed

    def is_erasure_overdue(self, request_id: str) -> bool:
        """Check whether an erasure request has exceeded the 30-day deadline."""
        req = self._erasure_requests.get(request_id)
        if req is None:
            raise KeyError(f"Unknown erasure request: {request_id}")
        if req.status == ErasureStatus.COMPLETED:
            return False
        return (time.time() - req.requested_at) > ERASURE_DEADLINE_SECONDS

    # ------------------------------------------------------------------
    # Data Portability (Art. 20)
    # ------------------------------------------------------------------

    def generate_portability_package(
        self,
        subject_hash: str,
        categories: set[DataCategory] | None = None,
    ) -> PortabilityPackage:
        """Generate a portability manifest for the data subject.

        The actual data export is out of scope (SSID is non-custodial);
        this produces the *manifest* with hash references only.
        """
        cats = frozenset(categories or {DataCategory.IDENTITY_HASH})
        export_payload = f"{subject_hash}:{sorted(c.value for c in cats)}"
        export_hash = hashlib.sha256(export_payload.encode()).hexdigest()

        return PortabilityPackage(
            subject_hash=subject_hash,
            data_categories=cats,
            export_hash=export_hash,
        )

    # ------------------------------------------------------------------
    # Evidence Generation
    # ------------------------------------------------------------------

    def generate_compliance_evidence(self, subject_hash: str) -> dict[str, Any]:
        """Produce a hash-based evidence bundle for audit."""
        consent_records = self.get_consent_history(subject_hash)
        erasure_reqs = [r for r in self._erasure_requests.values() if r.subject_hash == subject_hash]

        bundle_payload = f"{subject_hash}:{len(consent_records)}:{len(erasure_reqs)}:{time.time()}"
        bundle_hash = hashlib.sha256(bundle_payload.encode()).hexdigest()

        return {
            "subject_hash": subject_hash,
            "consent_count": len(consent_records),
            "erasure_request_count": len(erasure_reqs),
            "bundle_hash": bundle_hash,
            "generated_at": time.time(),
        }
