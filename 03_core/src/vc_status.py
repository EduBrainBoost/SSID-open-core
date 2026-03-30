"""
VC Status / Revocation List.

Maintains an in-memory revocation registry for Verifiable Credentials.
stdlib-only, fail-closed, non-custodial.
"""

import hashlib
import time
from typing import Dict, Set


# ---------------------------------------------------------------------------
# In-memory revocation registry
# ---------------------------------------------------------------------------
_revoked: Dict[str, dict] = {}   # vc_id -> revocation record


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def revoke(vc_id: str, reason: str = "unspecified") -> dict:
    """
    Revoke a Verifiable Credential by its ID.

    Args:
        vc_id: The credential identifier (urn:uuid:...).
        reason: Human-readable reason.

    Returns:
        Revocation record.

    Raises:
        ValueError if already revoked or invalid input.
    """
    if not isinstance(vc_id, str) or not vc_id:
        raise ValueError("vc_id must be a non-empty string")
    if vc_id in _revoked:
        raise ValueError(f"Credential already revoked: {vc_id}")

    record = {
        "vc_id": vc_id,
        "vc_id_hash": hashlib.sha3_256(vc_id.encode("utf-8")).hexdigest(),
        "reason": reason,
        "revoked_at": _now_iso(),
    }
    _revoked[vc_id] = record
    return record


def is_revoked(vc_id: str) -> bool:
    """Check whether a credential has been revoked."""
    return vc_id in _revoked


def get_status(vc_id: str) -> dict:
    """
    Get the status of a credential.

    Returns:
        {"vc_id": ..., "status": "active"|"revoked", ...}
    """
    if not isinstance(vc_id, str) or not vc_id:
        raise ValueError("vc_id must be a non-empty string")
    if vc_id in _revoked:
        return {**_revoked[vc_id], "status": "revoked"}
    return {"vc_id": vc_id, "status": "active"}


def list_revoked() -> list:
    """Return all revocation records."""
    return list(_revoked.values())


def reset_registry() -> None:
    """Clear the revocation registry (test helper)."""
    _revoked.clear()
