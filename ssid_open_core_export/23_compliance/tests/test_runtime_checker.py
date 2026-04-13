"""Tests for 23_compliance.src.runtime_checker."""

import pathlib
import sys

sys.path.insert(
    0,
    str(pathlib.Path(__file__).resolve().parent.parent / "src"),
)

from runtime_checker import (
    ComplianceChecker,
    ComplianceFinding,
    PIIDetector,
    SanctionsScreener,
    SecretScanner,
    Severity,
)

# ------------------------------------------------------------------
# SanctionsScreener
# ------------------------------------------------------------------


class TestSanctionsScreener:
    def test_no_match_returns_info(self):
        ss = SanctionsScreener()
        f = ss.screen("clean_entity")
        assert f.severity is Severity.INFO

    def test_match_returns_block(self):
        ss = SanctionsScreener()
        ss.add_entity("bad_actor")
        f = ss.screen("bad_actor")
        assert f.severity is Severity.BLOCK
        assert f.category == "sanctions"

    def test_case_insensitive(self):
        ss = SanctionsScreener()
        ss.add_entity("Evil Corp")
        f = ss.screen("evil corp")
        assert f.severity is Severity.BLOCK

    def test_hash_entity_deterministic(self):
        h1 = SanctionsScreener.hash_entity("test")
        h2 = SanctionsScreener.hash_entity("test")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_add_hash_directly(self):
        ss = SanctionsScreener()
        h = SanctionsScreener.hash_entity("target")
        ss.add_hash(h)
        f = ss.screen("target")
        assert f.severity is Severity.BLOCK

    def test_no_raw_pii_in_finding(self):
        ss = SanctionsScreener()
        ss.add_entity("John Doe")
        f = ss.screen("John Doe")
        assert "John Doe" not in f.detail
        assert f.evidence_hash  # hash present


# ------------------------------------------------------------------
# PIIDetector
# ------------------------------------------------------------------


class TestPIIDetector:
    def test_detects_email(self):
        det = PIIDetector()
        findings = det.scan("contact user@example.com please")
        assert len(findings) >= 1
        assert any(f.category == "pii" for f in findings)
        # Raw PII must NOT appear in detail
        assert all("user@example.com" not in f.detail for f in findings)

    def test_detects_ssn(self):
        det = PIIDetector()
        findings = det.scan("SSN: 123-45-6789")
        assert len(findings) >= 1
        assert any("ssn" in f.detail for f in findings)

    def test_detects_phone(self):
        det = PIIDetector()
        findings = det.scan("Call +1-555-867-5309")
        assert len(findings) >= 1

    def test_clean_text_no_findings(self):
        det = PIIDetector()
        findings = det.scan("This is perfectly clean text.")
        assert len(findings) == 0

    def test_redact_replaces_email(self):
        det = PIIDetector()
        result = det.redact("send to user@example.com now")
        assert "user@example.com" not in result
        assert "[REDACTED]" in result

    def test_redact_replaces_ssn(self):
        det = PIIDetector()
        result = det.redact("SSN: 123-45-6789")
        assert "123-45-6789" not in result

    def test_all_findings_are_block(self):
        det = PIIDetector()
        findings = det.scan("email: a@b.com SSN: 111-22-3333")
        assert all(f.severity is Severity.BLOCK for f in findings)


# ------------------------------------------------------------------
# SecretScanner
# ------------------------------------------------------------------


class TestSecretScanner:
    def test_detects_aws_key(self):
        scanner = SecretScanner()
        findings = scanner.scan("key=AKIAIOSFODNN7EXAMPLE")
        assert len(findings) >= 1
        assert any(f.category == "secret" for f in findings)

    def test_detects_generic_secret(self):
        scanner = SecretScanner()
        findings = scanner.scan("password=hunter2")
        assert len(findings) >= 1

    def test_detects_private_key(self):
        scanner = SecretScanner()
        findings = scanner.scan("-----BEGIN RSA PRIVATE KEY-----")
        assert len(findings) >= 1

    def test_clean_text(self):
        scanner = SecretScanner()
        findings = scanner.scan("just some normal code")
        assert len(findings) == 0

    def test_no_raw_secret_in_detail(self):
        scanner = SecretScanner()
        findings = scanner.scan("api_key=super_secret_value_123")
        for f in findings:
            assert "super_secret_value_123" not in f.detail


# ------------------------------------------------------------------
# ComplianceChecker (unified)
# ------------------------------------------------------------------


class TestComplianceChecker:
    def test_clean_entity_and_text(self):
        cc = ComplianceChecker()
        findings = cc.check_all("clean_org", "no issues here")
        assert not cc.has_block(findings)

    def test_sanctions_block_propagates(self):
        ss = SanctionsScreener()
        ss.add_entity("blocked_org")
        cc = ComplianceChecker(sanctions_screener=ss)
        findings = cc.check_entity("blocked_org")
        assert cc.has_block(findings)

    def test_pii_block_propagates(self):
        cc = ComplianceChecker()
        findings = cc.check_text("email me at bad@actor.com")
        assert cc.has_block(findings)

    def test_secret_block_propagates(self):
        cc = ComplianceChecker()
        findings = cc.check_text("password=oops")
        assert cc.has_block(findings)

    def test_check_all_combines(self):
        ss = SanctionsScreener()
        ss.add_entity("evil")
        cc = ComplianceChecker(sanctions_screener=ss)
        findings = cc.check_all("evil", "password=x")
        blocks = [f for f in findings if f.severity is Severity.BLOCK]
        assert len(blocks) >= 2  # sanctions + secret

    def test_finding_to_dict(self):
        f = ComplianceFinding(
            severity=Severity.BLOCK,
            category="test",
            detail="detail",
            evidence_hash="abc",
        )
        d = f.to_dict()
        assert d["severity"] == "BLOCK"
        assert d["evidence_hash"] == "abc"
