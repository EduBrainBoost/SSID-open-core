"""OpenCore public SDK — identity schemas."""
from __future__ import annotations
from .public_interface import SchemaContract


class DIDSchema(SchemaContract):
    """Public DID (Decentralized Identifier) schema."""

    def __init__(self) -> None:
        super().__init__("did_schema", "1.0.0")

    def create_synthetic_did(self) -> dict:
        return {
            "id": "did:example:synthetic123",
            "type": "ED25519",
            "publicKeyMultibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "controller": "https://example.com/issuer",
        }


class VCSchema(SchemaContract):
    """Public Verifiable Credential schema."""

    def __init__(self) -> None:
        super().__init__("vc_schema", "1.0.0")

    def create_synthetic_vc(self) -> dict:
        return {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential"],
            "credentialSubject": {
                "id": "did:example:subject123",
                "name": "Synthetic Test Subject",
            },
            "issuer": "did:example:issuer456",
            "issuanceDate": "2026-01-01T00:00:00Z",
        }


class IdentityScoreSchema(SchemaContract):
    """Public identity scoring interface."""

    def __init__(self) -> None:
        super().__init__("identity_score_schema", "1.0.0")

    def calculate_synthetic_score(self) -> dict:
        return {
            "score": 0.85,
            "range": {"min": 0.0, "max": 1.0},
            "factors": ["completeness", "verification", "recency"],
            "synthetic": True,
        }
