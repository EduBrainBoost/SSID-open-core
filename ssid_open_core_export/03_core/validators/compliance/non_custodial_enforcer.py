"""
Non-Custodial Runtime Enforcer (SWARM-03 / GAP-F005)

Validates that the SSID platform maintains non-custodial architecture constraints
at runtime. Ensures:

- No PII is stored in plaintext (only SHA3-256 hashes or proof references)
- No custody patterns exist in operation names
- No direct private key access occurs

References:
    23_compliance/frameworks/gdpr/gdpr_controls.yaml — GDPR-C-007 (Art. 25)
    Core contract: Non-Custodial — NIEMALS PII speichern (nur SHA3-256-Hashes)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ViolationType(Enum):
    """Categories of non-custodial violations."""

    PII_STORAGE = "pii_storage_detected"
    CUSTODY_PATTERN = "custody_pattern_detected"
    DIRECT_KEY_ACCESS = "direct_key_access"
    RAW_DOCUMENT_STORAGE = "raw_document_storage"


@dataclass(frozen=True)
class Violation:
    """Single enforcement violation record."""

    violation_type: str
    field_or_operation: str
    detail: str
    remedy: str
    severity: str = "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_type": self.violation_type,
            "field_or_operation": self.field_or_operation,
            "detail": self.detail,
            "remedy": self.remedy,
            "severity": self.severity,
        }


@dataclass
class EnforcementResult:
    """Result of an enforcement check."""

    passed: bool
    violations: list[Violation] = field(default_factory=list)
    enforcer: str = "NonCustodialEnforcer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "enforcer": self.enforcer,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
        }


# SHA3-256 produces 64 hex characters; SHA-256 also 64 hex characters
_HASH_HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")

# Proof reference patterns (DID, CID, URN)
_PROOF_PATTERNS = [
    re.compile(r"^did:"),
    re.compile(r"^bafy"),  # IPFS CID v1
    re.compile(r"^Qm[1-9A-HJ-NP-Za-km-z]{44}$"),  # IPFS CID v0
    re.compile(r"^urn:ssid:"),  # SSID internal proof URN
    re.compile(r"^proof:"),  # Generic proof reference
]


class NonCustodialEnforcer:
    """Validates that the system never stores PII or holds custody.

    Implements runtime enforcement for:
        - GAP-F005: Non-Custodial Runtime Enforcer
        - GDPR-C-007: Privacy by design (Art. 25)
        - Core contract: Non-Custodial principle
    """

    # Operations that imply custody — must never appear in SSID
    FORBIDDEN_OPERATIONS: list[str] = [
        "store_private_key",
        "save_credential",
        "persist_identity",
        "cache_personal_data",
        "write_pii",
        "store_document",
        "save_raw_biometric",
        "persist_session_token",
        "store_password",
        "cache_kyc_result",
    ]

    # Field names that indicate PII content
    PII_FIELD_INDICATORS: list[str] = [
        "name",
        "email",
        "phone",
        "address",
        "ssn",
        "passport",
        "dob",
        "birth",
        "national_id",
        "tax_id",
        "iban",
        "credit_card",
        "biometric",
        "face_image",
        "fingerprint",
        "full_name",
        "first_name",
        "last_name",
        "maiden_name",
        "social_security",
        "driver_license",
        "ip_address",
    ]

    def validate_no_pii_storage(self, data: dict[str, Any]) -> EnforcementResult:
        """Check that no PII is stored in plaintext — only hashes/proofs allowed.

        Args:
            data: Dictionary of field names to values to be persisted.

        Returns:
            EnforcementResult with any PII storage violations.
        """
        violations: list[Violation] = []

        for key, value in data.items():
            if not isinstance(value, str) or len(value) == 0:
                continue

            # Hashes and proof references are always allowed
            if self._is_hash_or_proof(value):
                continue

            # Check if the field name suggests PII content
            if self._looks_like_pii(key):
                violations.append(
                    Violation(
                        violation_type=ViolationType.PII_STORAGE.value,
                        field_or_operation=key,
                        detail=f"Field '{key}' contains non-hashed value (length={len(value)})",
                        remedy="Replace with SHA3-256 hash: hashlib.sha3_256(value.encode()).hexdigest()",
                        severity="critical",
                    )
                )

        return EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_no_custody(self, operation: str) -> EnforcementResult:
        """Check that no custody patterns exist in the operation name.

        Args:
            operation: The operation identifier to check.

        Returns:
            EnforcementResult with any custody pattern violations.
        """
        violations: list[Violation] = []
        op_lower = operation.lower()

        for pattern in self.FORBIDDEN_OPERATIONS:
            if pattern in op_lower:
                violations.append(
                    Violation(
                        violation_type=ViolationType.CUSTODY_PATTERN.value,
                        field_or_operation=operation,
                        detail=f"Forbidden custody pattern '{pattern}' in operation",
                        remedy="Use non-custodial alternative: hash, proof, or DID reference",
                        severity="critical",
                    )
                )

        return EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_no_direct_key_access(self, operation: str, params: dict | None = None) -> EnforcementResult:
        """Validate that no direct private key access is attempted.

        Args:
            operation: The operation identifier.
            params: Optional parameters that might contain key material.

        Returns:
            EnforcementResult with any key access violations.
        """
        violations: list[Violation] = []

        key_patterns = ["private_key", "secret_key", "signing_key", "master_key", "seed_phrase"]
        op_lower = operation.lower()

        for kp in key_patterns:
            if kp in op_lower:
                violations.append(
                    Violation(
                        violation_type=ViolationType.DIRECT_KEY_ACCESS.value,
                        field_or_operation=operation,
                        detail=f"Direct key access pattern '{kp}' detected",
                        remedy="Use vault-delegated signing; never access keys directly",
                        severity="critical",
                    )
                )

        if params:
            for param_key, _param_value in params.items():
                for kp in key_patterns:
                    if kp in param_key.lower():
                        violations.append(
                            Violation(
                                violation_type=ViolationType.DIRECT_KEY_ACCESS.value,
                                field_or_operation=param_key,
                                detail=f"Parameter '{param_key}' contains key material reference",
                                remedy="Remove key material from parameters; use vault reference instead",
                                severity="critical",
                            )
                        )

        return EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def enforce_all(self, data: dict[str, Any], operation: str, params: dict | None = None) -> EnforcementResult:
        """Run all non-custodial checks and return combined result.

        Args:
            data: Data fields to persist.
            operation: Operation identifier.
            params: Optional operation parameters.

        Returns:
            Combined EnforcementResult with all violations.
        """
        all_violations: list[Violation] = []

        pii_result = self.validate_no_pii_storage(data)
        all_violations.extend(pii_result.violations)

        custody_result = self.validate_no_custody(operation)
        all_violations.extend(custody_result.violations)

        key_result = self.validate_no_direct_key_access(operation, params)
        all_violations.extend(key_result.violations)

        return EnforcementResult(
            passed=len(all_violations) == 0,
            violations=all_violations,
        )

    @staticmethod
    def hash_pii(value: str) -> str:
        """Utility: convert a PII value to its SHA3-256 hash.

        This is the ONLY acceptable way to handle PII in SSID.
        """
        return hashlib.sha3_256(value.encode("utf-8")).hexdigest()

    def _is_hash_or_proof(self, value: str) -> bool:
        """Check if value is a hash (64 hex chars) or proof reference."""
        if _HASH_HEX_64.match(value):
            return True
        return any(p.match(value) for p in _PROOF_PATTERNS)

    def _looks_like_pii(self, key: str) -> bool:
        """Check if a field name indicates PII content."""
        key_lower = key.lower()
        return any(ind in key_lower for ind in self.PII_FIELD_INDICATORS)
