"""Shared evidence helper for all SSID skills."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def sha256_of(data: str) -> str:
    """Return SHA-256 hex digest of the given string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def make_evidence(
    skill_id: str,
    status: str,
    details: dict[str, Any],
    file_affected: str | None = None,
    sha256_before: str | None = None,
    sha256_after: str | None = None,
) -> dict[str, Any]:
    """Build a standard SSID evidence record."""
    payload = json.dumps(details, sort_keys=True)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "skill_id": skill_id,
        "status": status,
        "details": details,
        "file_affected": file_affected,
        "sha256_before": sha256_before,
        "sha256_after": sha256_after,
        "evidence_hash": sha256_of(payload),
    }


def result(status: str, evidence: dict[str, Any], message: str = "") -> dict[str, Any]:
    """Standard skill return value."""
    return {
        "status": status,
        "message": message,
        "evidence_ref": evidence.get("evidence_hash", ""),
        "evidence": evidence,
    }
