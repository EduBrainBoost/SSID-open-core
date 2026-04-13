"""Zero-time auth — JWT decode and validation for Admin API."""

from __future__ import annotations

import json
import os
from typing import Any


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload (header.payload.signature) without verification for dev.
    Production MUST verify against JWKS."""
    import base64

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    # Add padding
    payload += "=" * (4 - len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)
    return json.loads(decoded)


def load_jwks(path: str | None = None) -> dict[str, Any]:
    """Load JWKS from file. Returns empty keyset if not found."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "14_zero_time_auth", "jwt", "jwks.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"keys": []}
