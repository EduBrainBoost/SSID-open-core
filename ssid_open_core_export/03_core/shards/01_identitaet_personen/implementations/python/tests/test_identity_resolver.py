#!/usr/bin/env python3
"""Tests for 01_identitaet_personen shard: IdentityResolver and Validator.

Covers DID registration, resolution, validation, non-custodial policy
enforcement, and evidence generation.

Root: 03_core | Shard: 01_identitaet_personen
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add the shard src to sys.path for imports
SHARD_SRC = Path(__file__).resolve().parent.parent / "src"
if str(SHARD_SRC) not in sys.path:
    sys.path.insert(0, str(SHARD_SRC))

from identity_resolver import IdentityResolver

# ---------------------------------------------------------------------------
# IdentityResolver tests
# ---------------------------------------------------------------------------


class TestIdentityResolverRegistration:
    """DID registration must validate documents and produce evidence."""

    def _valid_did_document(self) -> dict:
        return {
            "id": "did:ssid:test123",
            "verificationMethod": [
                {
                    "id": "did:ssid:test123#key-1",
                    "type": "Ed25519VerificationKey2020",
                    "controller": "did:ssid:test123",
                    "publicKeyMultibase": "z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
                }
            ],
            "authentication": ["did:ssid:test123#key-1"],
            "versionId": 1,
        }

    def test_register_valid_document(self) -> None:
        resolver = IdentityResolver()
        doc = self._valid_did_document()
        result = resolver.register("did:ssid:test123", doc)
        assert result["did"] == "did:ssid:test123"
        assert result["operation"] == "register"
        assert len(result["content_hash"]) == 64, "SHA-256 hash expected"
        assert result["timestamp_utc"], "Timestamp must be non-empty"

    def test_resolve_after_register(self) -> None:
        resolver = IdentityResolver()
        doc = self._valid_did_document()
        resolver.register("did:ssid:test123", doc)
        resolved = resolver.resolve("did:ssid:test123")
        assert resolved is not None
        assert resolved["document"]["id"] == "did:ssid:test123"

    def test_resolve_unknown_did_returns_none(self) -> None:
        resolver = IdentityResolver()
        result = resolver.resolve("did:ssid:nonexistent")
        assert result is None

    def test_content_hash_is_deterministic(self) -> None:
        resolver = IdentityResolver()
        doc = self._valid_did_document()
        r1 = resolver.register("did:ssid:det1", doc)
        resolver2 = IdentityResolver()
        r2 = resolver2.register("did:ssid:det1", doc)
        assert r1["content_hash"] == r2["content_hash"]


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

try:
    # Module may be named with leading digits; use importlib
    import importlib.util

    _spec = importlib.util.spec_from_file_location("identitaet_module", SHARD_SRC / "01_identitaet_personen_module.py")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    Validator = _mod.Validator
except Exception:
    Validator = None


@pytest.mark.skipif(Validator is None, reason="Validator module not loadable")
class TestValidator:
    """Validator must enforce non-custodial policy and produce evidence."""

    def test_validate_with_valid_inputs(self) -> None:
        v = Validator()
        result = v.validate(data_hash="abc123", schema_id="schema-v1")
        assert result["valid"] is True
        assert result["domain"] == "01_identitaet_personen"

    def test_validate_with_empty_hash_fails(self) -> None:
        v = Validator()
        result = v.validate(data_hash="", schema_id="schema-v1")
        assert result["valid"] is False

    def test_check_policy_non_custodial(self) -> None:
        v = Validator()
        assert v.check_policy("non_custodial", {"non_custodial": "true"}) is True
        assert v.check_policy("non_custodial", {"non_custodial": "false"}) is False

    def test_check_policy_hash_only(self) -> None:
        v = Validator()
        assert v.check_policy("hash_only", {"hash_only": "true"}) is True

    def test_report_accumulates_validations(self) -> None:
        v = Validator()
        v.validate("h1", "s1")
        v.validate("h2", "s2")
        report = v.report()
        assert len(report) == 2

    def test_create_evidence_has_sha256(self) -> None:
        v = Validator()
        evidence = v.create_evidence("test_operation")
        assert len(evidence["sha256"]) == 64
        assert evidence["domain"] == "01_identitaet_personen"
        assert evidence["root"] == "03_core"
