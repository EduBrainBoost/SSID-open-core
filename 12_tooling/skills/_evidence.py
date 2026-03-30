"""Shared evidence helper for all SSID skills."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def sha256_of(data: str) -> str:
    """Return SHA-256 hex digest of the given string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def make_evidence(
    skill_id: str,
    status: str,
    details: Dict[str, Any],
    file_affected: Optional[str] = None,
    sha256_before: Optional[str] = None,
    sha256_after: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standard SSID evidence record."""
    payload = json.dumps(details, sort_keys=True)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill_id": skill_id,
        "status": status,
        "details": details,
        "file_affected": file_affected,
        "sha256_before": sha256_before,
        "sha256_after": sha256_after,
        "evidence_hash": sha256_of(payload),
    }


def result(status: str, evidence: Dict[str, Any], message: str = "") -> Dict[str, Any]:
    """Standard skill return value."""
    return {
        "status": status,
        "message": message,
        "evidence_ref": evidence.get("evidence_hash", ""),
        "evidence": evidence,
    }
