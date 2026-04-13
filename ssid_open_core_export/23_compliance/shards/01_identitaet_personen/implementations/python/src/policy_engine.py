"""
SSID Policy Engine — Runtime Policy Enforcement
Root: 23_compliance | Shard: 01_identitaet_personen

Enforces SSID core policies at runtime:
- hash_only: No PII in any payload
- non_custodial: No custody operations
- jurisdiction: Blocked jurisdictions
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class PolicyViolation:
    policy_id: str
    description: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    payload_hash: str
    timestamp_utc: str


class PolicyEngine:
    """Runtime policy enforcement for SSID operations."""

    BLOCKED_JURISDICTIONS = {"IR", "KP", "SY", "CU"}

    PII_PATTERNS = {
        "email",
        "phone",
        "phone_number",
        "address",
        "street",
        "date_of_birth",
        "dateOfBirth",
        "ssn",
        "social_security",
        "passport_number",
        "national_id",
        "first_name",
        "last_name",
        "full_name",
        "name",
    }

    def __init__(self):
        self._violations: list[PolicyViolation] = []
        self._checks_performed = 0

    def check_hash_only(self, payload: dict) -> list[PolicyViolation]:
        """Verify no PII fields exist in payload."""
        self._checks_performed += 1
        violations = []
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        found_pii = self._scan_for_pii(payload)
        for field_path in found_pii:
            v = PolicyViolation(
                policy_id="hash_only",
                description=f"PII field detected: {field_path}",
                severity="CRITICAL",
                payload_hash=payload_hash,
                timestamp_utc=datetime.now(UTC).isoformat(),
            )
            violations.append(v)
            self._violations.append(v)

        return violations

    def check_non_custodial(self, operation: dict) -> list[PolicyViolation]:
        """Verify operation doesn't involve custody."""
        self._checks_performed += 1
        violations = []
        custody_indicators = {"store_raw_data", "hold_funds", "manage_keys_for_user", "escrow"}

        op_type = operation.get("type", "")
        if op_type in custody_indicators:
            v = PolicyViolation(
                policy_id="non_custodial",
                description=f"Custody operation attempted: {op_type}",
                severity="CRITICAL",
                payload_hash=hashlib.sha256(json.dumps(operation, sort_keys=True).encode()).hexdigest(),
                timestamp_utc=datetime.now(UTC).isoformat(),
            )
            violations.append(v)
            self._violations.append(v)

        return violations

    def check_jurisdiction(self, country_code: str) -> list[PolicyViolation]:
        """Verify jurisdiction is not blocked."""
        self._checks_performed += 1
        violations = []

        if country_code.upper() in self.BLOCKED_JURISDICTIONS:
            v = PolicyViolation(
                policy_id="jurisdiction",
                description=f"Blocked jurisdiction: {country_code}",
                severity="CRITICAL",
                payload_hash=hashlib.sha256(country_code.encode()).hexdigest(),
                timestamp_utc=datetime.now(UTC).isoformat(),
            )
            violations.append(v)
            self._violations.append(v)

        return violations

    def enforce_all(self, payload: dict, operation: dict, country_code: str = "DE") -> dict:
        """Run all policy checks. Returns enforcement result."""
        all_violations = []
        all_violations.extend(self.check_hash_only(payload))
        all_violations.extend(self.check_non_custodial(operation))
        all_violations.extend(self.check_jurisdiction(country_code))

        return {
            "allowed": len(all_violations) == 0,
            "violations_count": len(all_violations),
            "violations": [
                {"policy": v.policy_id, "description": v.description, "severity": v.severity} for v in all_violations
            ],
            "timestamp_utc": datetime.now(UTC).isoformat(),
        }

    def _scan_for_pii(self, obj: dict, prefix: str = "") -> list[str]:
        """Recursively scan for PII field names."""
        found = []
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if key.lower() in self.PII_PATTERNS:
                found.append(path)
            if isinstance(value, dict):
                found.extend(self._scan_for_pii(value, path))
        return found

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def checks_performed(self) -> int:
        return self._checks_performed
