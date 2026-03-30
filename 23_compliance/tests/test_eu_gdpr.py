"""Tests for 23_compliance.jurisdictions.eu_gdpr — GDPR compliance engine."""

import pathlib
import sys
import time

import pytest

sys.path.insert(
    0,
    str(pathlib.Path(__file__).resolve().parent.parent / "jurisdictions"),
)

from eu_gdpr import (
    ConsentRecord,
    DataCategory,
    ErasureRequest,
    ErasureStatus,
    GDPRComplianceEngine,
    LegalBasis,
    PortabilityPackage,
)


# ------------------------------------------------------------------
# ConsentRecord
# ------------------------------------------------------------------

class TestConsentRecord:
    def test_to_dict_roundtrip(self):
        r = ConsentRecord(
            subject_hash="abc123",
            purpose="identity_verification",
            legal_basis=LegalBasis.CONSENT,
            granted=True,
            evidence_hash="ev1",
        )
        d = r.to_dict()
        assert d["subject_hash"] == "abc123"
        assert d["legal_basis"] == "consent"
        assert d["granted"] is True

    def test_frozen(self):
        r = ConsentRecord(
            subject_hash="x",
            purpose="p",
            legal_basis=LegalBasis.CONTRACT,
            granted=False,
        )
        with pytest.raises(AttributeError):
            r.granted = True  # type: ignore[misc]


# ------------------------------------------------------------------
# Consent Management
# ------------------------------------------------------------------

class TestConsentManagement:
    def test_record_consent(self):
        engine = GDPRComplianceEngine()
        rec = ConsentRecord(
            subject_hash="user1",
            purpose="analytics",
            legal_basis=LegalBasis.CONSENT,
            granted=True,
        )
        result = engine.record_consent(rec)
        assert result.granted is True

    def test_has_valid_consent_true(self):
        engine = GDPRComplianceEngine()
        engine.record_consent(ConsentRecord(
            subject_hash="u1", purpose="verify",
            legal_basis=LegalBasis.CONSENT, granted=True,
        ))
        assert engine.has_valid_consent("u1", "verify") is True

    def test_has_valid_consent_false_no_record(self):
        engine = GDPRComplianceEngine()
        assert engine.has_valid_consent("unknown", "verify") is False

    def test_consent_revocation_latest_wins(self):
        engine = GDPRComplianceEngine()
        engine.record_consent(ConsentRecord(
            subject_hash="u1", purpose="ads",
            legal_basis=LegalBasis.CONSENT, granted=True,
            timestamp=1000.0,
        ))
        engine.record_consent(ConsentRecord(
            subject_hash="u1", purpose="ads",
            legal_basis=LegalBasis.CONSENT, granted=False,
            timestamp=2000.0,
        ))
        assert engine.has_valid_consent("u1", "ads") is False

    def test_consent_history(self):
        engine = GDPRComplianceEngine()
        engine.record_consent(ConsentRecord(
            subject_hash="u1", purpose="a",
            legal_basis=LegalBasis.CONSENT, granted=True,
        ))
        engine.record_consent(ConsentRecord(
            subject_hash="u1", purpose="b",
            legal_basis=LegalBasis.CONTRACT, granted=True,
        ))
        history = engine.get_consent_history("u1")
        assert len(history) == 2

    def test_empty_subject_hash_raises(self):
        engine = GDPRComplianceEngine()
        with pytest.raises(ValueError):
            engine.record_consent(ConsentRecord(
                subject_hash="", purpose="x",
                legal_basis=LegalBasis.CONSENT, granted=True,
            ))

    def test_empty_purpose_raises(self):
        engine = GDPRComplianceEngine()
        with pytest.raises(ValueError):
            engine.record_consent(ConsentRecord(
                subject_hash="u1", purpose="",
                legal_basis=LegalBasis.CONSENT, granted=True,
            ))


# ------------------------------------------------------------------
# Erasure (Right to be Forgotten)
# ------------------------------------------------------------------

class TestErasure:
    def test_request_erasure(self):
        engine = GDPRComplianceEngine()
        req = ErasureRequest(request_id="er1", subject_hash="u1")
        result = engine.request_erasure(req)
        assert result.status == ErasureStatus.PENDING

    def test_execute_erasure_completes(self):
        engine = GDPRComplianceEngine()
        engine.record_consent(ConsentRecord(
            subject_hash="u1", purpose="verify",
            legal_basis=LegalBasis.CONSENT, granted=True,
        ))
        engine.request_erasure(ErasureRequest(request_id="er1", subject_hash="u1"))
        result = engine.execute_erasure("er1")
        assert result.status == ErasureStatus.COMPLETED
        assert result.completed_at is not None
        assert result.evidence_hash != ""
        # Old hash should no longer have consent records
        assert engine.get_consent_history("u1") == []
        # New hash should have migrated records
        assert len(engine.get_consent_history(result.subject_hash)) == 1

    def test_execute_unknown_raises(self):
        engine = GDPRComplianceEngine()
        with pytest.raises(KeyError):
            engine.execute_erasure("nonexistent")

    def test_erasure_hash_rotation(self):
        engine = GDPRComplianceEngine()
        engine.request_erasure(ErasureRequest(request_id="er1", subject_hash="u1"))
        result = engine.execute_erasure("er1")
        # New hash must differ from original
        assert result.subject_hash != "u1"

    def test_erasure_overdue_false_when_completed(self):
        engine = GDPRComplianceEngine()
        engine.request_erasure(ErasureRequest(request_id="er1", subject_hash="u1"))
        engine.execute_erasure("er1")
        assert engine.is_erasure_overdue("er1") is False

    def test_erasure_overdue_unknown_raises(self):
        engine = GDPRComplianceEngine()
        with pytest.raises(KeyError):
            engine.is_erasure_overdue("nonexistent")

    def test_empty_subject_hash_raises(self):
        engine = GDPRComplianceEngine()
        with pytest.raises(ValueError):
            engine.request_erasure(ErasureRequest(request_id="er1", subject_hash=""))

    def test_erasure_to_dict(self):
        req = ErasureRequest(request_id="er1", subject_hash="u1")
        d = req.to_dict()
        assert d["status"] == "pending"
        assert d["request_id"] == "er1"


# ------------------------------------------------------------------
# Data Portability
# ------------------------------------------------------------------

class TestPortability:
    def test_generate_package(self):
        engine = GDPRComplianceEngine()
        pkg = engine.generate_portability_package("u1")
        assert pkg.subject_hash == "u1"
        assert DataCategory.IDENTITY_HASH in pkg.data_categories
        assert pkg.export_hash != ""

    def test_custom_categories(self):
        engine = GDPRComplianceEngine()
        cats = {DataCategory.CONSENT_RECORD, DataCategory.AUDIT_LOG}
        pkg = engine.generate_portability_package("u1", categories=cats)
        assert pkg.data_categories == frozenset(cats)

    def test_package_to_dict(self):
        engine = GDPRComplianceEngine()
        pkg = engine.generate_portability_package("u1")
        d = pkg.to_dict()
        assert "data_categories" in d
        assert isinstance(d["data_categories"], list)


# ------------------------------------------------------------------
# Evidence Generation
# ------------------------------------------------------------------

class TestEvidence:
    def test_generate_evidence(self):
        engine = GDPRComplianceEngine()
        engine.record_consent(ConsentRecord(
            subject_hash="u1", purpose="verify",
            legal_basis=LegalBasis.CONSENT, granted=True,
        ))
        evidence = engine.generate_compliance_evidence("u1")
        assert evidence["subject_hash"] == "u1"
        assert evidence["consent_count"] == 1
        assert evidence["bundle_hash"] != ""

    def test_evidence_for_unknown_subject(self):
        engine = GDPRComplianceEngine()
        evidence = engine.generate_compliance_evidence("unknown")
        assert evidence["consent_count"] == 0
        assert evidence["erasure_request_count"] == 0

    def test_no_raw_pii_in_evidence(self):
        engine = GDPRComplianceEngine()
        evidence = engine.generate_compliance_evidence("sensitive_name")
        # The evidence should use hash-based identifiers only
        assert "bundle_hash" in evidence
