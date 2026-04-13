"""
Proof-Only Verification Engine
SoT v4.1.0 | ROOT-24-LOCK | Module: 03_core

SSID receives only proof/pass/credential/status from providers.
No PII storage, no payment intermediation, no custody.

Cross-references:
  - 19_adapters/providers/provider_registry.yaml (provider capabilities)
  - 23_compliance/policies/jurisdiction_blacklist.yaml (banned jurisdictions)
  - 23_compliance/policies/proof_only_verification_policy.yaml (policy rules)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class VerificationStatus(Enum):
    """Verification outcome states."""

    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNKNOWN_PROVIDER = "unknown_provider"
    PROVIDER_NOT_PROOF_ONLY = "provider_not_proof_only"
    BANNED_JURISDICTION = "banned_jurisdiction"
    PENDING = "pending"


class RevocationStatus(Enum):
    """Revocation states for a proof."""

    ACTIVE = "active"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


@dataclass
class ProofResult:
    """
    Immutable result of a proof verification.

    Contains NO PII -- only hashes, status, and metadata.
    raw_pii_present must always remain False for SSID compliance.
    """

    proof_id: str
    provider_id: str
    subject_hash: str  # SHA3-256 hash of subject identifier, never PII
    proof_type: str
    issued_at: datetime
    expires_at: datetime | None
    revocation_status: RevocationStatus
    verification_status: VerificationStatus
    evidence_hash: str
    raw_pii_present: bool = False

    def __post_init__(self) -> None:
        if self.raw_pii_present:
            raise ValueError("SSID COMPLIANCE VIOLATION: raw_pii_present must be False. SSID must never store PII.")


@dataclass
class ProviderCapability:
    """Parsed provider capability record from registry YAML."""

    provider_id: str
    legal_name: str
    category: str
    payment_flow: str
    user_pays_directly: bool | str  # bool or "conditional"
    proof_type: str
    verification_method: str
    supports_revocation_check: bool
    supports_expiry_check: bool
    supports_country_restrictions: bool
    proof_only_mode: bool
    pii_handling: str
    status: str
    governance_state: str


class ProviderRegistryLoader:
    """
    Loads and validates the provider registry YAML.

    Enforces:
    - All providers must have required fields
    - Fail-closed: unknown providers are rejected
    """

    def __init__(self, registry_path: str | Path | None = None) -> None:
        if registry_path is None:
            # Default: relative to repo root
            registry_path = Path(__file__).resolve().parents[3] / ("19_adapters/providers/provider_registry.yaml")
        self._path = Path(registry_path)
        self._providers: dict[str, ProviderCapability] = {}
        self._architecture: dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        """Load and parse the registry YAML."""
        if not self._path.exists():
            raise FileNotFoundError(f"Provider registry not found: {self._path}")

        with open(self._path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        self._architecture = data.get("architecture", {})

        for entry in data.get("providers", []):
            pid = entry["provider_id"]
            cap = ProviderCapability(
                provider_id=pid,
                legal_name=entry["legal_name"],
                category=entry["category"],
                payment_flow=entry["payment_flow"],
                user_pays_directly=entry["user_pays_directly"],
                proof_type=entry["proof_type"],
                verification_method=entry["verification_method"],
                supports_revocation_check=entry.get("supports_revocation_check", False),
                supports_expiry_check=entry.get("supports_expiry_check", False),
                supports_country_restrictions=entry.get("supports_country_restrictions", False),
                proof_only_mode=entry.get("proof_only_mode", False),
                pii_handling=entry.get("pii_handling", "unknown"),
                status=entry.get("status", "unknown"),
                governance_state=entry.get("governance_state", "unknown"),
            )
            self._providers[pid] = cap

        self._loaded = True

    @property
    def providers(self) -> dict[str, ProviderCapability]:
        if not self._loaded:
            self.load()
        return dict(self._providers)

    @property
    def architecture(self) -> dict[str, Any]:
        if not self._loaded:
            self.load()
        return dict(self._architecture)

    def get_provider(self, provider_id: str) -> ProviderCapability | None:
        """Get a single provider by ID. Returns None if not found."""
        if not self._loaded:
            self.load()
        return self._providers.get(provider_id)

    def get_proof_only_providers(self) -> list[ProviderCapability]:
        """Return only providers with proof_only_mode=True."""
        if not self._loaded:
            self.load()
        return [p for p in self._providers.values() if p.proof_only_mode]

    def get_direct_pay_providers(self) -> list[ProviderCapability]:
        """Return only providers where user_pays_directly is True."""
        if not self._loaded:
            self.load()
        return [p for p in self._providers.values() if p.user_pays_directly is True]


class JurisdictionChecker:
    """
    Loads jurisdiction blacklist and checks country eligibility.

    Cross-ref: 23_compliance/policies/jurisdiction_blacklist.yaml
    """

    def __init__(self, blacklist_path: str | Path | None = None) -> None:
        if blacklist_path is None:
            blacklist_path = Path(__file__).resolve().parents[3] / (
                "23_compliance/policies/jurisdiction_blacklist.yaml"
            )
        self._path = Path(blacklist_path)
        self._blacklisted: set[str] = set()
        self._high_risk: set[str] = set()
        self._loaded = False

    def load(self) -> None:
        """Load the jurisdiction blacklist."""
        if not self._path.exists():
            raise FileNotFoundError(f"Jurisdiction blacklist not found: {self._path}")

        with open(self._path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        for entry in data.get("blacklisted", []):
            self._blacklisted.add(entry["code"])

        for entry in data.get("sanctioned_regions", []):
            self._blacklisted.add(entry["code"])

        for entry in data.get("high_risk", []):
            self._high_risk.add(entry["code"])

        self._loaded = True

    def is_banned(self, country_code: str) -> bool:
        """Check if a country code is fully banned (blacklisted or sanctioned region)."""
        if not self._loaded:
            self.load()
        return country_code.upper() in self._blacklisted

    def is_high_risk(self, country_code: str) -> bool:
        """Check if a country code is high-risk (requires enhanced due diligence)."""
        if not self._loaded:
            self.load()
        return country_code.upper() in self._high_risk


class ProofVerifier:
    """
    Proof-Only Verification Engine.

    Fail-closed design:
    - Unknown providers -> REJECTED
    - Providers without proof_only_mode -> REJECTED
    - Expired proofs -> REJECTED
    - Revoked proofs -> REJECTED
    - Banned jurisdictions -> REJECTED
    """

    def __init__(
        self,
        registry: ProviderRegistryLoader | None = None,
        jurisdiction_checker: JurisdictionChecker | None = None,
    ) -> None:
        self._registry = registry or ProviderRegistryLoader()
        self._jurisdiction = jurisdiction_checker or JurisdictionChecker()

    def verify_proof(
        self,
        proof_id: str,
        provider_id: str,
        subject_hash: str,
        proof_type: str,
        issued_at: datetime,
        expires_at: datetime | None = None,
        revocation_status: str = "active",
        country_code: str | None = None,
    ) -> ProofResult:
        """
        Verify a proof submission.

        Performs all checks in fail-closed order:
        1. Provider known?
        2. Provider proof-only mode?
        3. Jurisdiction check
        4. Revocation check
        5. Expiry check

        Returns a ProofResult with appropriate VerificationStatus.
        """
        # 1. Provider known?
        provider = self._registry.get_provider(provider_id)
        if provider is None:
            return self._build_result(
                proof_id=proof_id,
                provider_id=provider_id,
                subject_hash=subject_hash,
                proof_type=proof_type,
                issued_at=issued_at,
                expires_at=expires_at,
                revocation_status=RevocationStatus.UNKNOWN,
                verification_status=VerificationStatus.UNKNOWN_PROVIDER,
            )

        # 2. Provider proof-only mode?
        if not provider.proof_only_mode:
            return self._build_result(
                proof_id=proof_id,
                provider_id=provider_id,
                subject_hash=subject_hash,
                proof_type=proof_type,
                issued_at=issued_at,
                expires_at=expires_at,
                revocation_status=RevocationStatus.UNKNOWN,
                verification_status=VerificationStatus.PROVIDER_NOT_PROOF_ONLY,
            )

        # 3. Jurisdiction check
        if country_code and self._jurisdiction.is_banned(country_code):
            return self._build_result(
                proof_id=proof_id,
                provider_id=provider_id,
                subject_hash=subject_hash,
                proof_type=proof_type,
                issued_at=issued_at,
                expires_at=expires_at,
                revocation_status=RevocationStatus(revocation_status),
                verification_status=VerificationStatus.BANNED_JURISDICTION,
            )

        # 4. Revocation check
        rev_status = RevocationStatus(revocation_status)
        if rev_status == RevocationStatus.REVOKED:
            return self._build_result(
                proof_id=proof_id,
                provider_id=provider_id,
                subject_hash=subject_hash,
                proof_type=proof_type,
                issued_at=issued_at,
                expires_at=expires_at,
                revocation_status=rev_status,
                verification_status=VerificationStatus.REVOKED,
            )

        # 5. Expiry check
        if expires_at is not None and expires_at < datetime.now(UTC):
            return self._build_result(
                proof_id=proof_id,
                provider_id=provider_id,
                subject_hash=subject_hash,
                proof_type=proof_type,
                issued_at=issued_at,
                expires_at=expires_at,
                revocation_status=rev_status,
                verification_status=VerificationStatus.EXPIRED,
            )

        # All checks passed
        return self._build_result(
            proof_id=proof_id,
            provider_id=provider_id,
            subject_hash=subject_hash,
            proof_type=proof_type,
            issued_at=issued_at,
            expires_at=expires_at,
            revocation_status=rev_status,
            verification_status=VerificationStatus.VERIFIED,
        )

    def check_revocation(self, revocation_status: str) -> RevocationStatus:
        """Parse and return revocation status."""
        return RevocationStatus(revocation_status)

    def check_expiry(self, expires_at: datetime | None) -> bool:
        """Return True if the proof is still valid (not expired)."""
        if expires_at is None:
            return True
        return expires_at >= datetime.now(UTC)

    def check_country_eligibility(self, country_code: str) -> bool:
        """Return True if the country is not banned."""
        return not self._jurisdiction.is_banned(country_code)

    @staticmethod
    def _build_result(
        proof_id: str,
        provider_id: str,
        subject_hash: str,
        proof_type: str,
        issued_at: datetime,
        expires_at: datetime | None,
        revocation_status: RevocationStatus,
        verification_status: VerificationStatus,
    ) -> ProofResult:
        """Build a ProofResult with computed evidence hash."""
        evidence_payload = f"{proof_id}:{provider_id}:{subject_hash}:{proof_type}:{verification_status.value}"
        evidence_hash = hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest()

        return ProofResult(
            proof_id=proof_id,
            provider_id=provider_id,
            subject_hash=subject_hash,
            proof_type=proof_type,
            issued_at=issued_at,
            expires_at=expires_at,
            revocation_status=revocation_status,
            verification_status=verification_status,
            evidence_hash=evidence_hash,
            raw_pii_present=False,
        )
