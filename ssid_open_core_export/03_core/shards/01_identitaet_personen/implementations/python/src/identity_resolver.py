"""
SSID Identity Resolver — Core DID Resolution & Validation
Root: 03_core | Shard: 01_identitaet_personen

Resolves DIDs, validates DID Documents, enforces non-custodial policy.
"""

import hashlib
import json
from datetime import UTC, datetime


class IdentityResolver:
    """Core identity resolution service for SSID DIDs."""

    def __init__(self):
        self._registry: dict[str, dict] = {}
        self._resolution_log: list[dict] = []

    def register(self, did: str, did_document: dict) -> dict:
        """Register a DID Document. Validates non-custodial constraints."""
        validation = self._validate_document(did_document)
        if not validation["valid"]:
            raise ValueError(f"DID Document validation failed: {validation['errors']}")

        doc_hash = hashlib.sha256(json.dumps(did_document, sort_keys=True).encode()).hexdigest()

        self._registry[did] = {
            "document": did_document,
            "content_hash": doc_hash,
            "registered_at": datetime.now(UTC).isoformat(),
            "version": did_document.get("versionId", 1),
        }

        return {
            "did": did,
            "operation": "register",
            "content_hash": doc_hash,
            "timestamp_utc": self._registry[did]["registered_at"],
        }

    def resolve(self, did: str) -> dict | None:
        """Resolve a DID to its DID Document."""
        entry = self._registry.get(did)
        if entry is None:
            self._log_resolution(did, success=False)
            return None

        doc = entry["document"]
        if not doc.get("active", True):
            self._log_resolution(did, success=False, reason="deactivated")
            return {"error": "deactivated", "did": did}

        self._log_resolution(did, success=True)
        return doc

    def verify_integrity(self, did: str) -> dict:
        """Verify the stored DID Document hasn't been tampered with."""
        entry = self._registry.get(did)
        if entry is None:
            return {"did": did, "integrity": "NOT_FOUND"}

        current_hash = hashlib.sha256(json.dumps(entry["document"], sort_keys=True).encode()).hexdigest()

        return {
            "did": did,
            "stored_hash": entry["content_hash"],
            "computed_hash": current_hash,
            "integrity": "PASS" if current_hash == entry["content_hash"] else "FAIL",
        }

    def _validate_document(self, doc: dict) -> dict:
        """Validate DID Document against SSID policies."""
        errors = []

        if "@context" not in doc:
            errors.append("missing @context")
        if "id" not in doc:
            errors.append("missing id")
        if "verificationMethod" not in doc:
            errors.append("missing verificationMethod")

        # Non-custodial check: no raw PII fields allowed
        pii_fields = {"name", "email", "phone", "address", "dateOfBirth", "ssn"}
        found_pii = pii_fields & set(doc.keys())
        if found_pii:
            errors.append(f"PII fields detected (non-custodial violation): {found_pii}")

        for vm in doc.get("verificationMethod", []):
            if "publicKeyJwk" not in vm and "publicKeyMultibase" not in vm:
                errors.append(f"verificationMethod {vm.get('id')} missing key material")

        return {"valid": len(errors) == 0, "errors": errors}

    def _log_resolution(self, did: str, success: bool, reason: str = "") -> None:
        self._resolution_log.append(
            {
                "did": did,
                "success": success,
                "reason": reason,
                "timestamp_utc": datetime.now(UTC).isoformat(),
            }
        )

    @property
    def resolution_count(self) -> int:
        return len(self._resolution_log)
