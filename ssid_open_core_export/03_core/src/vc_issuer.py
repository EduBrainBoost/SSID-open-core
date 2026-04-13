"""
Verifiable Credential Issuer — SD-JWT VC format.

Issues credentials with selective disclosure support.
stdlib-only, non-custodial, hash-only (no PII), fail-closed.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _b64url(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _build_sd_hash(claim_name: str, claim_value: Any, salt: str) -> str:
    """Build a selective-disclosure hash for one claim."""
    disclosure = json.dumps([salt, claim_name, claim_value], separators=(",", ":"))
    return _sha256(disclosure)


# ---------------------------------------------------------------------------
# SD-JWT VC Issuance
# ---------------------------------------------------------------------------


def issue(
    issuer_did: str,
    subject_did: str,
    claims: dict[str, Any],
    *,
    credential_type: str = "VerifiableCredential",
    selective_fields: list[str] | None = None,
    signing_key_hex: str,
) -> dict:
    """
    Issue a Verifiable Credential in SD-JWT VC format.

    Args:
        issuer_did: DID of the issuer.
        subject_did: DID of the subject (holder).
        claims: Key-value claims (values are hashed, never stored raw).
        credential_type: VC type string.
        selective_fields: Claim keys eligible for selective disclosure.
        signing_key_hex: Hex-encoded signing key for HMAC signature.

    Returns:
        dict with keys: credential, disclosures, signature.

    Raises:
        ValueError on invalid inputs (fail-closed).
    """
    if not issuer_did or not subject_did:
        raise ValueError("issuer_did and subject_did are required")
    if not claims:
        raise ValueError("claims must be non-empty")
    if not signing_key_hex:
        raise ValueError("signing_key_hex is required")

    selective = set(selective_fields or [])
    now = _now_iso()
    vc_id = f"urn:uuid:{uuid.uuid4()}"

    # Hash all claim values (non-custodial — no PII stored)
    hashed_claims: dict[str, str] = {}
    disclosures: dict[str, dict] = {}

    for name, value in claims.items():
        value_hash = _sha256(json.dumps(value, separators=(",", ":")))
        hashed_claims[name] = value_hash

        if name in selective:
            salt = uuid.uuid4().hex
            sd_hash = _build_sd_hash(name, value_hash, salt)
            disclosures[name] = {
                "salt": salt,
                "sd_hash": sd_hash,
                "claim_hash": value_hash,
            }

    # Build credential payload
    credential = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": [credential_type],
        "id": vc_id,
        "issuer": issuer_did,
        "issuanceDate": now,
        "credentialSubject": {
            "id": subject_did,
            **hashed_claims,
        },
    }

    if disclosures:
        credential["_sd"] = list(disclosures.keys())

    # HMAC signature (deterministic, stdlib-only)
    payload_bytes = json.dumps(credential, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(
        bytes.fromhex(signing_key_hex),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return {
        "credential": credential,
        "disclosures": disclosures,
        "signature": sig,
        "format": "sd-jwt-vc",
    }
