"""
Verifiable Credential Verifier.

Verifies credential integrity and presentations.
stdlib-only, fail-closed, non-custodial.
"""

import hashlib
import hmac
import json
from typing import Dict, Optional

try:
    from . import vc_status
except ImportError:
    import vc_status  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_signature(credential: dict, signing_key_hex: str) -> str:
    """Recompute HMAC signature for a credential payload."""
    payload = json.dumps(credential, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(
        bytes.fromhex(signing_key_hex),
        payload,
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_credential(
    vc_envelope: dict,
    signing_key_hex: str,
) -> dict:
    """
    Verify a Verifiable Credential.

    Checks:
        1. Structural validity.
        2. Signature integrity (HMAC).
        3. Revocation status.

    Args:
        vc_envelope: The envelope returned by vc_issuer.issue().
        signing_key_hex: Hex-encoded signing key for HMAC verification.

    Returns:
        {"valid": bool, "checks": {...}, "error": str|None}
    """
    checks = {
        "structure": False,
        "signature": False,
        "revocation": False,
    }

    try:
        # 1. Structure
        credential = vc_envelope.get("credential")
        signature = vc_envelope.get("signature")
        if not credential or not signature:
            return {"valid": False, "checks": checks, "error": "Missing credential or signature"}

        required = {"@context", "type", "id", "issuer", "credentialSubject"}
        if not required.issubset(set(credential.keys())):
            return {"valid": False, "checks": checks, "error": "Credential missing required fields"}
        checks["structure"] = True

        # 2. Signature
        expected_sig = _compute_signature(credential, signing_key_hex)
        if not hmac.compare_digest(signature, expected_sig):
            return {"valid": False, "checks": checks, "error": "Signature mismatch"}
        checks["signature"] = True

        # 3. Revocation
        vc_id = credential["id"]
        if vc_status.is_revoked(vc_id):
            return {"valid": False, "checks": checks, "error": f"Credential revoked: {vc_id}"}
        checks["revocation"] = True

        return {"valid": True, "checks": checks, "error": None}

    except Exception as exc:
        # Fail-closed
        return {"valid": False, "checks": checks, "error": str(exc)}


def verify_presentation(
    vc_envelope: dict,
    signing_key_hex: str,
    *,
    disclosed_fields: Optional[list] = None,
) -> dict:
    """
    Verify a Verifiable Presentation (selective disclosure).

    If disclosed_fields is given, verifies only those fields are present
    in credentialSubject (beyond 'id').

    Returns:
        {"valid": bool, "checks": {...}, "error": str|None}
    """
    result = verify_credential(vc_envelope, signing_key_hex)
    if not result["valid"]:
        return result

    if disclosed_fields is not None:
        subject = vc_envelope["credential"]["credentialSubject"]
        subject_fields = set(subject.keys()) - {"id"}
        disclosed_set = set(disclosed_fields)
        if not disclosed_set.issubset(subject_fields):
            missing = disclosed_set - subject_fields
            return {
                "valid": False,
                "checks": result["checks"],
                "error": f"Disclosed fields not in credential: {missing}",
            }

    return result
