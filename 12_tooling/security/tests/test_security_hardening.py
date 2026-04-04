#!/usr/bin/env python3
"""Tests for 12_tooling.security — SBOM, scanning, signature verification, supply chain.

Verifies:
  - sbom_generator: CycloneDX structure, component deduplication, secret scrubbing.
  - dependency_scanner: ScanReport dataclass, offline scan, severity classification.
  - signature_verifier: Hash computation, HMAC sign/verify, sealed evidence checks.
  - supply_chain_validator: Provenance validation, SBOM integrity, reproducibility.

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# Make parent security package importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import UTC

from security.dependency_scanner import (
    ScanReport,
    VulnerabilityFinding,
    _classify_severity,
    scan_components,
)
from security.sbom_generator import (
    _check_secrets,
    _parse_requirements,
    generate_cyclonedx_sbom,
    scan_root,
)
from security.signature_verifier import (
    ALLOWED_HASH_ALGORITHMS,
    FORBIDDEN_HASH_ALGORITHMS,
    compute_hash,
    hmac_sign,
    hmac_verify,
    verify_hash,
    verify_sealed_evidence,
)
from security.supply_chain_validator import (
    ValidationReport,
    compare_sboms,
    validate_artifact_manifest,
    validate_provenance,
    validate_sbom_integrity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_requirements(tmp_path: Path) -> Path:
    """Write a minimal requirements.txt to tmp_path and return its path."""
    content = (
        "# Auto-generated\n"
        "requests==2.31.0\n"
        "cryptography==41.0.5\n"
        "pydantic==2.5.0\n"
        "  # blank after strip  \n"
        "-r other.txt\n"
    )
    p = tmp_path / "requirements.txt"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture()
def minimal_sealed_record() -> dict[str, Any]:
    payload = {"data": "hello world"}
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = hashlib.sha256(payload_bytes).hexdigest()
    record: dict[str, Any] = {
        "evidence_id": "e-001",
        "algorithm": "sha256",
        "hash": h,
        "sealed_at": "2026-03-15T10:00:00Z",
        "payload": payload,
    }
    # Add HMAC signature
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    secret = b"test-secret-key"
    sig = _hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    record["signature"] = sig
    return record


@pytest.fixture()
def minimal_sbom(tmp_path: Path) -> Path:
    """Write a minimal CycloneDX SBOM JSON to tmp_path."""
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "components": [
            {"name": "requests", "version": "2.31.0", "purl": "pkg:pypi/requests@2.31.0"},
            {"name": "cryptography", "version": "41.0.5", "purl": "pkg:pypi/cryptography@41.0.5"},
        ],
    }
    p = tmp_path / "sbom.json"
    p.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
    return p


@pytest.fixture()
def valid_provenance() -> dict[str, Any]:
    return {
        "builder": "github-actions",
        "build_timestamp": "2026-03-15T10:00:00Z",
        "source_repo": "github.com/ssid/ssid",
        "commit_sha": "a" * 40,
    }


# ============================================================
# sbom_generator tests
# ============================================================


class TestSbomGenerator:
    def test_parse_requirements_basic(self, tmp_requirements: Path) -> None:
        components = _parse_requirements(tmp_requirements)
        names = [c["name"] for c in components]
        assert "requests" in names
        assert "cryptography" in names
        assert "pydantic" in names

    def test_parse_requirements_excludes_comments(self, tmp_requirements: Path) -> None:
        components = _parse_requirements(tmp_requirements)
        for c in components:
            assert not c["name"].startswith("#")

    def test_parse_requirements_correct_version(self, tmp_requirements: Path) -> None:
        components = _parse_requirements(tmp_requirements)
        req = next(c for c in components if c["name"] == "requests")
        assert req["version"] == "2.31.0"

    def test_parse_requirements_purl_format(self, tmp_requirements: Path) -> None:
        components = _parse_requirements(tmp_requirements)
        for c in components:
            assert c["purl"].startswith("pkg:pypi/")

    def test_check_secrets_clean(self) -> None:
        clean = '{"name": "requests", "version": "2.31.0"}'
        assert _check_secrets(clean) == []

    def test_check_secrets_aws_key(self) -> None:
        dirty = '{"key": "AKIAIOSFODNN7EXAMPLE"}'
        violations = _check_secrets(dirty)
        assert any("AKIA" in v for v in violations)

    def test_check_secrets_github_token(self) -> None:
        dirty = '{"token": "ghp_' + "a" * 36 + '"}'
        violations = _check_secrets(dirty)
        assert len(violations) >= 1

    def test_generate_cyclonedx_sbom_structure(self, tmp_path: Path) -> None:
        # Create a fake root with a requirements.txt
        root = tmp_path / "03_core"
        root.mkdir()
        (root / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
        sbom = generate_cyclonedx_sbom(repo_root=tmp_path, root_filter="03_core")
        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.4"
        assert isinstance(sbom["components"], list)

    def test_generate_cyclonedx_sbom_metadata(self, tmp_path: Path) -> None:
        sbom = generate_cyclonedx_sbom(repo_root=tmp_path)
        assert "metadata" in sbom
        assert sbom["metadata"]["component"]["name"] == "SSID"

    def test_scan_root_empty_dir(self, tmp_path: Path) -> None:
        """A root with no lockfiles should return an empty component list."""
        empty_root = tmp_path / "01_ai_layer"
        empty_root.mkdir()
        components = scan_root(empty_root)
        assert components == []

    def test_scan_root_with_requirements(self, tmp_path: Path, tmp_requirements: Path) -> None:
        root = tmp_path / "12_tooling"
        root.mkdir()
        (root / "requirements.txt").write_text("numpy==1.26.0\n", encoding="utf-8")
        components = scan_root(root)
        assert any(c["name"] == "numpy" for c in components)

    def test_scan_root_deduplicates(self, tmp_path: Path) -> None:
        root = tmp_path / "test_root"
        root.mkdir()
        # Same package listed twice
        (root / "requirements.txt").write_text("boto3==1.34.0\nboto3==1.34.0\n", encoding="utf-8")
        components = scan_root(root)
        boto3 = [c for c in components if c["name"] == "boto3"]
        assert len(boto3) == 1


# ============================================================
# dependency_scanner tests
# ============================================================


class TestDependencyScanner:
    def test_classify_severity_cvss_critical(self) -> None:
        assert _classify_severity(9.5, "") == "critical"

    def test_classify_severity_cvss_high(self) -> None:
        assert _classify_severity(7.2, "") == "high"

    def test_classify_severity_cvss_medium(self) -> None:
        assert _classify_severity(5.0, "") == "medium"

    def test_classify_severity_cvss_low(self) -> None:
        assert _classify_severity(2.0, "") == "low"

    def test_classify_severity_raw_string(self) -> None:
        assert _classify_severity(None, "high") == "high"
        assert _classify_severity(None, "CRITICAL") == "critical"

    def test_classify_severity_unknown(self) -> None:
        assert _classify_severity(None, "informational") == "unknown"

    def test_scan_components_offline_empty(self) -> None:
        report = scan_components([], online=False)
        assert isinstance(report, ScanReport)
        assert report.total_packages == 0
        assert report.total_vulnerabilities == 0
        assert report.offline is True

    def test_scan_components_offline_counts(self) -> None:
        components = [
            {"name": "requests", "version": "2.31.0", "purl": "pkg:pypi/requests@2.31.0"},
            {"name": "cryptography", "version": "41.0.5", "purl": "pkg:pypi/cryptography@41.0.5"},
        ]
        report = scan_components(components, online=False)
        assert report.total_packages == 2
        assert report.total_vulnerabilities == 0  # offline = no findings

    def test_scan_report_severity_sum(self) -> None:
        finding = VulnerabilityFinding(
            package_name="old-pkg",
            package_version="0.1.0",
            ecosystem="pypi",
            vuln_id="CVE-2020-0001",
            severity="critical",
            cvss_score=9.8,
            summary="Remote code execution",
            advisory_url="https://example.com/cve-2020-0001",
        )
        report = ScanReport(
            scanned_at="2026-03-15T00:00:00Z",
            total_packages=1,
            total_vulnerabilities=1,
            critical=1,
            high=0,
            medium=0,
            low=0,
            unknown=0,
            findings=[finding],
        )
        assert report.critical == 1
        assert report.findings[0].vuln_id == "CVE-2020-0001"


# ============================================================
# signature_verifier tests
# ============================================================


class TestSignatureVerifier:
    def test_compute_hash_sha256(self) -> None:
        result = compute_hash(b"hello", "sha256")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert result == expected

    def test_compute_hash_sha512(self) -> None:
        result = compute_hash(b"data", "sha512")
        assert len(result) == 128  # 64 bytes hex

    def test_compute_hash_forbidden_md5(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            compute_hash(b"data", "md5")

    def test_compute_hash_forbidden_sha1(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            compute_hash(b"data", "sha1")

    def test_compute_hash_unknown_algorithm(self) -> None:
        with pytest.raises(ValueError):
            compute_hash(b"data", "blake2b")

    def test_verify_hash_match(self) -> None:
        expected = hashlib.sha256(b"test").hexdigest()
        assert verify_hash(b"test", expected, "sha256") is True

    def test_verify_hash_mismatch(self) -> None:
        assert verify_hash(b"test", "0" * 64, "sha256") is False

    def test_verify_hash_forbidden_returns_false(self) -> None:
        assert verify_hash(b"test", "aa" * 16, "md5") is False

    def test_hmac_sign_produces_hex(self) -> None:
        sig = hmac_sign(b"payload", b"secret")
        assert len(sig) == 64  # SHA-256 hex
        int(sig, 16)  # Must be valid hex

    def test_hmac_verify_correct(self) -> None:
        sig = hmac_sign(b"payload", b"secret")
        assert hmac_verify(b"payload", sig, b"secret") is True

    def test_hmac_verify_wrong_payload(self) -> None:
        sig = hmac_sign(b"payload", b"secret")
        assert hmac_verify(b"wrong", sig, b"secret") is False

    def test_hmac_verify_wrong_secret(self) -> None:
        sig = hmac_sign(b"payload", b"secret")
        assert hmac_verify(b"payload", sig, b"wrongsecret") is False

    def test_verify_sealed_evidence_pass(self, minimal_sealed_record: dict[str, Any]) -> None:
        report = verify_sealed_evidence(minimal_sealed_record, hmac_secret=b"test-secret-key")
        assert report.overall_pass is True

    def test_verify_sealed_evidence_missing_fields(self) -> None:
        bad_record = {"evidence_id": "e-001"}  # Missing required fields
        report = verify_sealed_evidence(bad_record)
        # Should fail on required_fields check
        checks_by_name = {r.check: r for r in report.results}
        assert not checks_by_name["required_fields"].passed

    def test_verify_sealed_evidence_forbidden_algorithm(self, minimal_sealed_record: dict[str, Any]) -> None:
        record = dict(minimal_sealed_record)
        record["algorithm"] = "md5"
        report = verify_sealed_evidence(record)
        checks_by_name = {r.check: r for r in report.results}
        assert not checks_by_name["hash_algorithm"].passed

    def test_verify_sealed_evidence_short_signature(self, minimal_sealed_record: dict[str, Any]) -> None:
        record = dict(minimal_sealed_record)
        record["signature"] = "ab12"  # Too short
        report = verify_sealed_evidence(record)
        checks_by_name = {r.check: r for r in report.results}
        assert not checks_by_name["signature_length"].passed

    def test_verify_sealed_evidence_hash_mismatch(self, minimal_sealed_record: dict[str, Any]) -> None:
        record = dict(minimal_sealed_record)
        record["hash"] = "0" * 64  # Wrong hash
        report = verify_sealed_evidence(record)
        checks_by_name = {r.check: r for r in report.results}
        assert not checks_by_name["payload_hash"].passed

    def test_allowed_hash_algorithms_complete(self) -> None:
        assert "sha256" in ALLOWED_HASH_ALGORITHMS
        assert "sha512" in ALLOWED_HASH_ALGORITHMS
        assert "sha3_256" in ALLOWED_HASH_ALGORITHMS

    def test_forbidden_hash_algorithms_complete(self) -> None:
        assert "md5" in FORBIDDEN_HASH_ALGORITHMS
        assert "sha1" in FORBIDDEN_HASH_ALGORITHMS


# ============================================================
# supply_chain_validator tests
# ============================================================


class TestSupplyChainValidator:
    def test_validate_provenance_valid(self, valid_provenance: dict[str, Any]) -> None:
        report = validate_provenance(valid_provenance)
        assert report.overall_pass is True

    def test_validate_provenance_missing_fields(self) -> None:
        report = validate_provenance({"builder": "github-actions"})
        assert report.overall_pass is False

    def test_validate_provenance_disallowed_builder(self, valid_provenance: dict[str, Any]) -> None:
        prov = dict(valid_provenance)
        prov["builder"] = "jenkins"
        report = validate_provenance(prov)
        assert report.overall_pass is False

    def test_validate_provenance_bad_commit_sha(self, valid_provenance: dict[str, Any]) -> None:
        prov = dict(valid_provenance)
        prov["commit_sha"] = "not-a-sha"
        report = validate_provenance(prov)
        assert report.overall_pass is False

    def test_validate_provenance_empty_repo(self, valid_provenance: dict[str, Any]) -> None:
        prov = dict(valid_provenance)
        prov["source_repo"] = ""
        report = validate_provenance(prov)
        assert report.overall_pass is False

    def test_validate_sbom_integrity_valid(self, minimal_sbom: Path) -> None:
        report = validate_sbom_integrity(minimal_sbom)
        assert report.overall_pass is True

    def test_validate_sbom_integrity_with_correct_hash(self, minimal_sbom: Path) -> None:
        import hashlib as _h

        expected = _h.sha256(minimal_sbom.read_bytes()).hexdigest()
        report = validate_sbom_integrity(minimal_sbom, expected_sha256=expected)
        assert report.overall_pass is True

    def test_validate_sbom_integrity_with_wrong_hash(self, minimal_sbom: Path) -> None:
        report = validate_sbom_integrity(minimal_sbom, expected_sha256="0" * 64)
        assert report.overall_pass is False

    def test_validate_sbom_integrity_missing_file(self, tmp_path: Path) -> None:
        report = validate_sbom_integrity(tmp_path / "nonexistent.json")
        assert report.overall_pass is False

    def test_validate_sbom_integrity_invalid_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("not json{{", encoding="utf-8")
        report = validate_sbom_integrity(bad)
        assert report.overall_pass is False

    def test_compare_sboms_identical(self, minimal_sbom: Path, tmp_path: Path) -> None:
        # Copy SBOM to a second file
        sbom_b = tmp_path / "sbom_b.json"
        sbom_b.write_bytes(minimal_sbom.read_bytes())
        report = compare_sboms(minimal_sbom, sbom_b)
        assert report.overall_pass is True

    def test_compare_sboms_different(self, minimal_sbom: Path, tmp_path: Path) -> None:
        sbom_b_data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "components": [
                {"name": "flask", "version": "3.0.0", "purl": "pkg:pypi/flask@3.0.0"},
            ],
        }
        sbom_b = tmp_path / "sbom_b.json"
        sbom_b.write_text(json.dumps(sbom_b_data), encoding="utf-8")
        report = compare_sboms(minimal_sbom, sbom_b)
        assert report.overall_pass is False

    def test_validate_artifact_manifest_valid(self, tmp_path: Path) -> None:
        # Create a real artifact file and manifest
        artifact = tmp_path / "dist" / "app.whl"
        artifact.parent.mkdir()
        artifact.write_bytes(b"fake wheel content")
        artifact_hash = hashlib.sha256(b"fake wheel content").hexdigest()

        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"artifacts": [{"path": "dist/app.whl", "sha256": artifact_hash}]}), encoding="utf-8"
        )

        report = validate_artifact_manifest(manifest)
        assert report.overall_pass is True

    def test_validate_artifact_manifest_hash_mismatch(self, tmp_path: Path) -> None:
        artifact = tmp_path / "dist" / "app.whl"
        artifact.parent.mkdir()
        artifact.write_bytes(b"real content")

        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"artifacts": [{"path": "dist/app.whl", "sha256": "0" * 64}]}), encoding="utf-8")

        report = validate_artifact_manifest(manifest)
        assert report.overall_pass is False

    def test_validate_artifact_manifest_missing_artifact(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"artifacts": [{"path": "dist/missing.whl", "sha256": "ab" * 32}]}), encoding="utf-8"
        )

        report = validate_artifact_manifest(manifest)
        assert report.overall_pass is False

    def test_validation_report_add_method(self) -> None:
        from datetime import datetime

        report = ValidationReport(
            validated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            subject="test",
            overall_pass=True,
        )
        report.add("check_a", True, "all good")
        report.add("check_b", False, "failed")
        assert report.overall_pass is False
        assert len(report.checks) == 2

    def test_validation_report_to_dict(self) -> None:
        from datetime import datetime

        report = ValidationReport(
            validated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            subject="sbom",
            overall_pass=True,
        )
        report.add("test_check", True, "ok")
        d = report.to_dict()
        assert "overall_pass" in d
        assert "checks" in d
        assert d["checks"][0]["name"] == "test_check"
