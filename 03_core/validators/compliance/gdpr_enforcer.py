"""
GDPR Runtime Enforcer (SWARM-03 / GAP-F006)

Validates GDPR compliance at runtime. Enforces:

- Consent validation (Art. 7)
- Data subject rights compliance (Art. 15-22)
- Retention policy enforcement (Art. 5(1)(e))
- Hash-only storage validation (Art. 25 — Privacy by Design)
- Lawful basis gate (Art. 5(1)(a))
- Special category data gate (Art. 9)

References:
    23_compliance/frameworks/gdpr/gdpr_controls.yaml
    23_compliance/frameworks/gdpr/gdpr_mapping.yaml
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GDPRViolationType(Enum):
    """GDPR-specific violation categories."""

    MISSING_CONSENT = "missing_consent"
    EXPIRED_CONSENT = "expired_consent"
    INVALID_LAWFUL_BASIS = "invalid_lawful_basis"
    RETENTION_EXCEEDED = "retention_exceeded"
    NO_RETENTION_POLICY = "no_retention_policy"
    RAW_PII_STORAGE = "raw_pii_storage"
    MISSING_SUBJECT_RIGHT = "missing_subject_right_handler"
    SPECIAL_CATEGORY_UNPROTECTED = "special_category_unprotected"
    MISSING_DPIA = "missing_dpia"


@dataclass(frozen=True)
class GDPRViolation:
    """Single GDPR enforcement violation."""

    violation_type: str
    article: str
    control_id: str
    field_or_operation: str
    detail: str
    remedy: str
    severity: str = "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_type": self.violation_type,
            "article": self.article,
            "control_id": self.control_id,
            "field_or_operation": self.field_or_operation,
            "detail": self.detail,
            "remedy": self.remedy,
            "severity": self.severity,
        }


@dataclass
class GDPREnforcementResult:
    """Result of a GDPR enforcement check."""

    passed: bool
    violations: List[GDPRViolation] = field(default_factory=list)
    enforcer: str = "GDPREnforcer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "enforcer": self.enforcer,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
        }


# Valid lawful bases per Art. 6(1) GDPR
LAWFUL_BASES = frozenset({
    "consent",           # Art. 6(1)(a)
    "contract",          # Art. 6(1)(b)
    "legal_obligation",  # Art. 6(1)(c)
    "vital_interests",   # Art. 6(1)(d)
    "public_task",       # Art. 6(1)(e)
    "legitimate_interest",  # Art. 6(1)(f)
})

# Data subject rights per Art. 15-22
REQUIRED_SUBJECT_RIGHTS = frozenset({
    "access",            # Art. 15
    "rectification",     # Art. 16
    "erasure",           # Art. 17
    "restriction",       # Art. 18
    "portability",       # Art. 20
    "objection",         # Art. 21
})

# Special category fields per Art. 9
SPECIAL_CATEGORY_INDICATORS = frozenset({
    "health", "biometric", "genetic", "racial", "ethnic",
    "political", "religious", "philosophical", "trade_union",
    "sexual_orientation", "criminal",
})

# Hash pattern (64 hex chars for SHA-256 / SHA3-256)
_HASH_HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")


class GDPREnforcer:
    """Validates GDPR compliance at runtime.

    Implements enforcement for:
        - GAP-F006: DSGVO/GDPR Runtime Enforcer
        - GDPR-C-001 through GDPR-C-012
    """

    def validate_consent(self, consent_record: Optional[Dict[str, Any]]) -> GDPREnforcementResult:
        """Validate that valid consent exists for a processing operation.

        Args:
            consent_record: Must contain 'granted', 'purpose', 'timestamp',
                            and optionally 'expires_at' (epoch seconds).

        Returns:
            GDPREnforcementResult with consent violations.
        """
        violations: List[GDPRViolation] = []

        if consent_record is None:
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.MISSING_CONSENT.value,
                article="Art. 7",
                control_id="GDPR-C-004",
                field_or_operation="consent_record",
                detail="No consent record provided for processing operation",
                remedy="Obtain explicit consent before processing",
            ))
            return GDPREnforcementResult(passed=False, violations=violations)

        if not consent_record.get("granted", False):
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.MISSING_CONSENT.value,
                article="Art. 7",
                control_id="GDPR-C-004",
                field_or_operation="consent_record.granted",
                detail="Consent not granted",
                remedy="Obtain explicit consent before processing",
            ))

        if not consent_record.get("purpose"):
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.MISSING_CONSENT.value,
                article="Art. 7",
                control_id="GDPR-C-004",
                field_or_operation="consent_record.purpose",
                detail="Consent purpose not specified",
                remedy="Specify processing purpose in consent record",
            ))

        expires_at = consent_record.get("expires_at")
        if expires_at is not None and isinstance(expires_at, (int, float)):
            if time.time() > expires_at:
                violations.append(GDPRViolation(
                    violation_type=GDPRViolationType.EXPIRED_CONSENT.value,
                    article="Art. 7",
                    control_id="GDPR-C-004",
                    field_or_operation="consent_record.expires_at",
                    detail="Consent has expired",
                    remedy="Request renewed consent from data subject",
                ))

        return GDPREnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_lawful_basis(self, lawful_basis: Optional[str]) -> GDPREnforcementResult:
        """Validate that a declared lawful basis is valid per Art. 6(1).

        Args:
            lawful_basis: The declared lawful basis identifier.

        Returns:
            GDPREnforcementResult with lawful basis violations.
        """
        violations: List[GDPRViolation] = []

        if not lawful_basis:
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.INVALID_LAWFUL_BASIS.value,
                article="Art. 5(1)(a)",
                control_id="GDPR-C-001",
                field_or_operation="lawful_basis",
                detail="No lawful basis declared for processing operation",
                remedy="Declare one of: consent, contract, legal_obligation, vital_interests, public_task, legitimate_interest",
            ))
        elif lawful_basis not in LAWFUL_BASES:
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.INVALID_LAWFUL_BASIS.value,
                article="Art. 5(1)(a)",
                control_id="GDPR-C-001",
                field_or_operation="lawful_basis",
                detail=f"Invalid lawful basis: '{lawful_basis}'",
                remedy=f"Use one of: {', '.join(sorted(LAWFUL_BASES))}",
            ))

        return GDPREnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_retention_policy(
        self,
        data_category: str,
        retention_policy: Optional[Dict[str, Any]],
        stored_since_epoch: Optional[float] = None,
    ) -> GDPREnforcementResult:
        """Validate retention policy exists and is not exceeded.

        Args:
            data_category: Category of data being stored.
            retention_policy: Must contain 'max_days' and 'purpose'.
            stored_since_epoch: When the data was first stored (epoch seconds).

        Returns:
            GDPREnforcementResult with retention violations.
        """
        violations: List[GDPRViolation] = []

        if retention_policy is None:
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.NO_RETENTION_POLICY.value,
                article="Art. 5(1)(e)",
                control_id="GDPR-C-003",
                field_or_operation=data_category,
                detail=f"No retention policy defined for data category '{data_category}'",
                remedy="Define retention policy with max_days and purpose",
            ))
            return GDPREnforcementResult(passed=False, violations=violations)

        max_days = retention_policy.get("max_days")
        if max_days is None or not isinstance(max_days, (int, float)) or max_days <= 0:
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.NO_RETENTION_POLICY.value,
                article="Art. 5(1)(e)",
                control_id="GDPR-C-003",
                field_or_operation=data_category,
                detail="Retention policy missing valid 'max_days'",
                remedy="Set a positive integer for max_days",
            ))

        if stored_since_epoch is not None and max_days is not None and isinstance(max_days, (int, float)):
            elapsed_days = (time.time() - stored_since_epoch) / 86400.0
            if elapsed_days > max_days:
                violations.append(GDPRViolation(
                    violation_type=GDPRViolationType.RETENTION_EXCEEDED.value,
                    article="Art. 5(1)(e)",
                    control_id="GDPR-C-003",
                    field_or_operation=data_category,
                    detail=f"Data stored for {elapsed_days:.1f} days, max allowed is {max_days}",
                    remedy="Delete or anonymize data that exceeds retention period",
                ))

        return GDPREnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_hash_only_storage(self, data: Dict[str, Any]) -> GDPREnforcementResult:
        """Validate that only hashes are stored, never raw PII.

        Args:
            data: Dictionary of field names to values.

        Returns:
            GDPREnforcementResult with hash-only violations.
        """
        violations: List[GDPRViolation] = []

        pii_fields = {
            "name", "email", "phone", "address", "ssn", "passport",
            "dob", "birth", "national_id", "full_name", "first_name",
            "last_name", "ip_address", "iban", "credit_card",
        }

        for key, value in data.items():
            if not isinstance(value, str) or len(value) == 0:
                continue

            key_lower = key.lower()
            is_pii_field = any(pii in key_lower for pii in pii_fields)

            if is_pii_field and not _HASH_HEX_64.match(value):
                violations.append(GDPRViolation(
                    violation_type=GDPRViolationType.RAW_PII_STORAGE.value,
                    article="Art. 25",
                    control_id="GDPR-C-007",
                    field_or_operation=key,
                    detail=f"Field '{key}' contains raw PII (not a hash)",
                    remedy="Hash value with SHA3-256 before storage",
                ))

        return GDPREnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_subject_rights_handlers(
        self,
        registered_handlers: Optional[List[str]],
    ) -> GDPREnforcementResult:
        """Validate that all required data subject rights have handlers.

        Args:
            registered_handlers: List of registered right handler identifiers.

        Returns:
            GDPREnforcementResult with missing handler violations.
        """
        violations: List[GDPRViolation] = []

        if registered_handlers is None:
            registered_handlers = []

        handler_set = frozenset(h.lower() for h in registered_handlers)
        missing = REQUIRED_SUBJECT_RIGHTS - handler_set

        for right in sorted(missing):
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.MISSING_SUBJECT_RIGHT.value,
                article="Art. 15-22",
                control_id="GDPR-C-006",
                field_or_operation=right,
                detail=f"No handler registered for data subject right: '{right}'",
                remedy=f"Register handler for '{right}' in subject rights API",
            ))

        return GDPREnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_special_category_protection(
        self,
        data_fields: List[str],
        has_explicit_consent: bool = False,
        has_dpia: bool = False,
    ) -> GDPREnforcementResult:
        """Validate that special category data has extra protection.

        Args:
            data_fields: List of field names being processed.
            has_explicit_consent: Whether explicit Art. 9(2)(a) consent exists.
            has_dpia: Whether a DPIA has been completed.

        Returns:
            GDPREnforcementResult with special category violations.
        """
        violations: List[GDPRViolation] = []

        special_fields = []
        for f in data_fields:
            f_lower = f.lower()
            if any(ind in f_lower for ind in SPECIAL_CATEGORY_INDICATORS):
                special_fields.append(f)

        if not special_fields:
            return GDPREnforcementResult(passed=True, violations=[])

        if not has_explicit_consent:
            for sf in special_fields:
                violations.append(GDPRViolation(
                    violation_type=GDPRViolationType.SPECIAL_CATEGORY_UNPROTECTED.value,
                    article="Art. 9",
                    control_id="GDPR-C-005",
                    field_or_operation=sf,
                    detail=f"Special category field '{sf}' processed without explicit consent",
                    remedy="Obtain Art. 9(2)(a) explicit consent before processing",
                ))

        if not has_dpia:
            violations.append(GDPRViolation(
                violation_type=GDPRViolationType.MISSING_DPIA.value,
                article="Art. 35",
                control_id="GDPR-C-011",
                field_or_operation="special_category_processing",
                detail="Special category data processing without completed DPIA",
                remedy="Complete Data Protection Impact Assessment before processing",
            ))

        return GDPREnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def enforce_all(
        self,
        data: Dict[str, Any],
        consent_record: Optional[Dict[str, Any]] = None,
        lawful_basis: Optional[str] = None,
        retention_policy: Optional[Dict[str, Any]] = None,
        data_category: str = "general",
        registered_handlers: Optional[List[str]] = None,
    ) -> GDPREnforcementResult:
        """Run all GDPR checks and return combined result.

        Args:
            data: Data fields to persist.
            consent_record: Consent information.
            lawful_basis: Declared lawful basis.
            retention_policy: Retention policy for data category.
            data_category: Category identifier for retention.
            registered_handlers: List of registered subject rights handlers.

        Returns:
            Combined GDPREnforcementResult.
        """
        all_violations: List[GDPRViolation] = []

        consent_result = self.validate_consent(consent_record)
        all_violations.extend(consent_result.violations)

        basis_result = self.validate_lawful_basis(lawful_basis)
        all_violations.extend(basis_result.violations)

        retention_result = self.validate_retention_policy(data_category, retention_policy)
        all_violations.extend(retention_result.violations)

        hash_result = self.validate_hash_only_storage(data)
        all_violations.extend(hash_result.violations)

        rights_result = self.validate_subject_rights_handlers(registered_handlers)
        all_violations.extend(rights_result.violations)

        return GDPREnforcementResult(
            passed=len(all_violations) == 0,
            violations=all_violations,
        )
