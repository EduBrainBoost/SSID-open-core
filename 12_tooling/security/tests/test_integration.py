#!/usr/bin/env python3
"""Integration tests for 12_tooling/security — SBOM → scanner → verifier chain.

Tests the full pipeline: generate SBOM → scan components → verify sealed evidence.
All tests use tmp_path for isolation and are runnable standalone.

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

# Make security package importable regardless of working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from security.sbom_generator import (
    _check_secrets,
    _parse_requirements,
    generate_cyclonedx_sbom,
    scan_root,
)
from security.dependency_scanner import (
    ScanReport,
    VulnerabilityFinding,
    _classify_severity,
    scan_components,
    scan_sbom_file,
)
from security.signature_verifier import (
    ALLOWED_HASH_ALGORITHMS,
    FORBIDDEN_HASH_ALGORITHMS,
    compute_hash,
    hmac_sign,
    hmac_verify,
    verify_hash,
    verify_sealed_evidence,
    verify_evidence_chain,
)
from security.supply_chain_validator import (
    ValidationReport,
    compare_sboms,
    validate_artifact_manifest,
    validate_provenance,
    validate_sbom_integrity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_requirements(tmp_path: Path, content: str) -> Path:
    """Write a requirements.txt file and return its path."""
    req = tmp_path / "requirements.txt"
    req.write_text(content, encoding="utf-8")
    return req


def _make_sbom(tmp_path: Path, components: list[dict]) -> Path:
    """Write a minimal CycloneDX SBOM JSON file and return its path."""
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": "urn:uuid:test-integration",
        "version": 1,
        "components": components,
    }
    p = tmp_path / "sbom.json"
    p.write_text(json.dumps(sbom), encoding="utf-8")
    return p


def _seal_record(record: dict, secret: bytes) -> dict:
    """Sign a record dict with HMAC-SHA256 and return it with 'signature' field."""
    payload = {k: v for k, v in record.items() if k != "signature"}
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac_sign(payload_bytes, secret)
    return {**record, "signature": sig}


# ---------------------------------------------------------------------------
# Test 1: SBOM generation from requirements.txt produces valid CycloneDX output
# ---------------------------------------------------------------------------

class TestSBOMGenerationFromRequirements:
    def test_sbom_generated_from_requirements_txt(self, tmp_path: Path) -> None:
        """SBOM generator reads requirements.txt and emits CycloneDX structure."""
        # Arrange: create a minimal root with requirements.txt
        root = tmp_path / "03_core"
        root.mkdir()
        (root / "requirements.txt").write_text(
            "requests==2.31.0\nurllib3==2.0.7\n", encoding="utf-8"
        )

        # Act
        sbom = generate_cyclonedx_sbom(repo_root=tmp_path, root_filter="03_core")

        # Assert structure
        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.4"
        components = sbom["components"]
        names = [c["name"] for c in components]
        assert "requests" in names
        assert "urllib3" in names

    def test_sbom_components_have_purl(self, tmp_path: Path) -> None:
        """Each SBOM component must include a purl field."""
        root = tmp_path / "08_identity_score"
        root.mkdir()
        (root / "requirements.txt").write_text("pydantic==2.5.0\n", encoding="utf-8")

        sbom = generate_cyclonedx_sbom(repo_root=tmp_path, root_filter="08_identity_score")

        for comp in sbom["components"]:
            assert "purl" in comp, f"Component {comp['name']} missing purl"
            assert comp["purl"].startswith("pkg:pypi/")


# ---------------------------------------------------------------------------
# Test 2: SBOM scanner → ScanReport chain works offline
# ---------------------------------------------------------------------------

class TestSBOMToScannerChain:
    def test_scan_sbom_file_offline_produces_report(self, tmp_path: Path) -> None:
        """scan_sbom_file in offline mode returns a ScanReport with correct totals."""
        components = [
            {"name": "requests", "version": "2.31.0", "purl": "pkg:pypi/requests@2.31.0"},
            {"name": "cryptography", "version": "41.0.0", "purl": "pkg:pypi/cryptography@41.0.0"},
        ]
        sbom_path = _make_sbom(tmp_path, components)

        report = scan_sbom_file(sbom_path, online=False)

        assert isinstance(report, ScanReport)
        assert report.total_packages == 2
        assert report.total_vulnerabilities == 0  # offline — no network calls
        assert report.offline is True

    def test_scan_components_empty_list_offline(self) -> None:
        """scan_components with empty list returns a report with zero packages."""
        report = scan_components([], online=False)

        assert report.total_packages == 0
        assert report.total_vulnerabilities == 0
        assert report.offline is True

    def test_severity_classification_from_cvss(self) -> None:
        """_classify_severity maps CVSS scores to canonical severity strings."""
        assert _classify_severity(9.5, "unknown") == "critical"
        assert _classify_severity(7.5, "unknown") == "high"
        assert _classify_severity(5.0, "unknown") == "medium"
        assert _classify_severity(2.0, "unknown") == "low"
        assert _classify_severity(None, "high") == "high"
        assert _classify_severity(None, "unknown") == "unknown"


# ---------------------------------------------------------------------------
# Test 3: Verifier chain — HMAC signing → sealed evidence verification
# ---------------------------------------------------------------------------

class TestSignerToVerifierChain:
    def test_hmac_sign_then_verify_passes(self) -> None:
        """A payload signed with hmac_sign passes hmac_verify."""
        secret = b"integration-test-secret-key"
        payload = b'{"evidence_id":"ev-001","data":"hello"}'

        sig = hmac_sign(payload, secret)
        assert hmac_verify(payload, sig, secret) is True

    def test_hmac_verify_rejects_tampered_payload(self) -> None:
        """hmac_verify returns False when payload is tampered after signing."""
        secret = b"key-for-tamper-test"
        original = b"original payload"
        tampered = b"tampered payload"

        sig = hmac_sign(original, secret)
        assert hmac_verify(tampered, sig, secret) is False

    def test_sealed_evidence_full_pass_with_secret(self) -> None:
        """A properly sealed evidence record passes all verification checks."""
        secret = b"seal-secret-0001"
        payload_data = {"user": "alice", "event": "login"}
        payload_json = json.dumps(payload_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        hash_hex = compute_hash(payload_json, "sha256")

        record: dict[str, Any] = {
            "evidence_id": "ev-integration-001",
            "hash": hash_hex,
            "algorithm": "sha256",
            "sealed_at": "2026-03-15T10:00:00Z",
            "payload": payload_data,
        }
        signed_record = _seal_record(record, secret)

        report = verify_sealed_evidence(signed_record, hmac_secret=secret)

        assert report.overall_pass is True
        failed = [r for r in report.results if not r.passed]
        assert not failed, f"Unexpected failures: {[r.detail for r in failed]}"

    def test_sealed_evidence_fails_with_wrong_secret(self) -> None:
        """A record signed with one secret fails verification with a different secret."""
        signing_secret = b"correct-secret"
        wrong_secret = b"wrong-secret"
        payload_data = {"event": "transfer"}
        payload_json = json.dumps(payload_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        hash_hex = compute_hash(payload_json, "sha256")

        record: dict[str, Any] = {
            "evidence_id": "ev-wrong-key",
            "hash": hash_hex,
            "algorithm": "sha256",
            "sealed_at": "2026-03-15T10:00:00Z",
            "payload": payload_data,
        }
        signed_record = _seal_record(record, signing_secret)

        report = verify_sealed_evidence(signed_record, hmac_secret=wrong_secret)

        hmac_result = next(r for r in report.results if r.check == "hmac_signature")
        assert hmac_result.passed is False

    def test_evidence_chain_batch_verification(self) -> None:
        """verify_evidence_chain processes multiple records and returns one report each."""
        secret = b"batch-chain-secret"
        records = []
        for i in range(3):
            payload_data = {"event": f"event-{i}"}
            payload_json = json.dumps(payload_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
            hash_hex = compute_hash(payload_json, "sha256")
            r: dict[str, Any] = {
                "evidence_id": f"ev-batch-{i:03d}",
                "hash": hash_hex,
                "algorithm": "sha256",
                "sealed_at": "2026-03-15T12:00:00Z",
                "payload": payload_data,
            }
            records.append(_seal_record(r, secret))

        reports = verify_evidence_chain(records, hmac_secret=secret)

        assert len(reports) == 3
        for rpt in reports:
            assert rpt.overall_pass is True


# ---------------------------------------------------------------------------
# Test 4: Supply chain → SBOM integrity cross-check
# ---------------------------------------------------------------------------

class TestSBOMIntegrityChain:
    def test_validate_sbom_integrity_with_correct_hash(self, tmp_path: Path) -> None:
        """validate_sbom_integrity passes when the hash matches SBOM file content."""
        sbom_content = json.dumps({"bomFormat": "CycloneDX", "components": []})
        sbom_path = tmp_path / "sbom.json"
        sbom_path.write_text(sbom_content, encoding="utf-8")

        correct_hash = hashlib.sha256(sbom_path.read_bytes()).hexdigest()

        report = validate_sbom_integrity(sbom_path, expected_sha256=correct_hash)

        assert report.overall_pass is True

    def test_validate_sbom_integrity_fails_with_wrong_hash(self, tmp_path: Path) -> None:
        """validate_sbom_integrity fails when the declared hash does not match."""
        sbom_path = tmp_path / "sbom_bad.json"
        sbom_path.write_text('{"bomFormat":"CycloneDX"}', encoding="utf-8")

        wrong_hash = "a" * 64  # invalid hash

        report = validate_sbom_integrity(sbom_path, expected_sha256=wrong_hash)

        assert report.overall_pass is False
