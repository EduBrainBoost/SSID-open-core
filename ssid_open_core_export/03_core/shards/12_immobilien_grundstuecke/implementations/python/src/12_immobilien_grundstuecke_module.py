"""Validator module for Immobilien & Grundstuecke."""

import hashlib
from datetime import UTC, datetime
from typing import Any


class Validator:
    """Core validation and policy enforcement for the Immobilien & Grundstuecke domain.

    Non-custodial: validates hashes only, never stores raw PII.
    """

    def __init__(self) -> None:
        self._reports: list[dict[str, Any]] = []

    def validate(self, data_hash: str, schema_id: str) -> dict[str, Any]:
        result = {
            "valid": bool(data_hash and schema_id),
            "data_hash": data_hash,
            "schema_id": schema_id,
            "domain": "12_immobilien_grundstuecke",
            "validated_utc": datetime.now(UTC).isoformat(),
        }
        self._reports.append(result)
        return result

    def check_policy(self, policy_id: str, context: dict[str, str]) -> bool:
        required = {"hash_only", "non_custodial"}
        if policy_id in required:
            return context.get(policy_id) == "true"
        return True

    def report(self) -> list[dict[str, Any]]:
        return list(self._reports)

    def create_evidence(self, operation: str) -> dict[str, str]:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "operation": operation,
            "domain": "12_immobilien_grundstuecke",
            "root": "03_core",
            "sha256": hashlib.sha256(operation.encode()).hexdigest(),
        }
