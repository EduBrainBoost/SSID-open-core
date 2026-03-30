#!/usr/bin/env python3
"""Tests for release_pipeline.py — Release Pipeline Manager.

Tests verify manifest creation, promotion gates, promotion flow,
rollback, and evidence integrity using in-memory fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_DIR = REPO_ROOT / "12_tooling" / "cli"
sys.path.insert(0, str(CLI_DIR))

from release_pipeline import (
    PROMOTION_ORDER,
    VALID_STATUSES,
    EvidenceCompleteGate,
    GateResult,
    NoPiiGate,
    PromotionGate,
    PromotionResult,
    ReleasePipeline,
    ReleaseManifest,
    RollbackRecord,
    SecretScanCleanGate,
    TestsGreenGate,
    default_gates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(**overrides) -> ReleaseManifest:
    defaults = {
        "version": "4.1.0",
        "sha": "abc1234567890def",
        "timestamp": "2026-03-15T00:00:00Z",
    }
    defaults.update(overrides)
    return ReleaseManifest(**defaults)


def _passing_context() -> dict:
    """Context where all gates pass."""
    return {
        "tests_green": True,
        "secret_scan_clean": True,
        "no_pii": True,
    }


# ---------------------------------------------------------------------------
# ReleaseManifest tests
# ---------------------------------------------------------------------------


class TestReleaseManifest:
    def test_create_with_defaults(self):
        m = _make_manifest()
        assert m.version == "4.1.0"
        assert m.sha == "abc1234567890def"
        assert m.status == "draft"
        assert m.release_id  # auto-generated
        assert m.artifacts == []
        assert m.evidence_hashes == []

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="Invalid status"):
            _make_manifest(status="invalid")

    def test_valid_statuses(self):
        for s in VALID_STATUSES:
            m = _make_manifest(status=s)
            assert m.status == s

    def test_integrity_hash_deterministic(self):
        m = _make_manifest(release_id="fixed123")
        h1 = m.integrity_hash()
        h2 = m.integrity_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex

    def test_integrity_hash_changes_with_status(self):
        m1 = _make_manifest(release_id="fixed123", status="draft")
        m2 = _make_manifest(release_id="fixed123", status="staging")
        assert m1.integrity_hash() != m2.integrity_hash()

    def test_to_dict_roundtrip(self):
        m = _make_manifest(artifacts=["file.txt"], evidence_hashes=["a" * 64])
        d = m.to_dict()
        m2 = ReleaseManifest.from_dict(d)
        assert m2.version == m.version
        assert m2.sha == m.sha
        assert m2.artifacts == m.artifacts
        assert m2.evidence_hashes == m.evidence_hashes
        assert m2.release_id == m.release_id

    def test_from_dict_ignores_unknown_keys(self):
        d = {
            "version": "1.0.0",
            "sha": "aaa",
            "timestamp": "2026-01-01T00:00:00Z",
            "unknown_field": "ignored",
        }
        m = ReleaseManifest.from_dict(d)
        assert m.version == "1.0.0"


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------


class TestGates:
    def test_tests_green_pass(self):
        m = _make_manifest()
        gate = TestsGreenGate()
        r = gate.check(m, {"tests_green": True})
        assert r.passed is True

    def test_tests_green_fail(self):
        m = _make_manifest()
        gate = TestsGreenGate()
        r = gate.check(m, {"tests_green": False})
        assert r.passed is False

    def test_tests_green_missing_context(self):
        m = _make_manifest()
        gate = TestsGreenGate()
        r = gate.check(m, {})
        assert r.passed is False

    def test_evidence_complete_pass(self):
        m = _make_manifest(evidence_hashes=["a" * 64])
        gate = EvidenceCompleteGate()
        r = gate.check(m)
        assert r.passed is True

    def test_evidence_complete_fail(self):
        m = _make_manifest()
        gate = EvidenceCompleteGate()
        r = gate.check(m)
        assert r.passed is False

    def test_secret_scan_clean(self):
        m = _make_manifest()
        gate = SecretScanCleanGate()
        assert gate.check(m, {"secret_scan_clean": True}).passed is True
        assert gate.check(m, {"secret_scan_clean": False}).passed is False

    def test_no_pii(self):
        m = _make_manifest()
        gate = NoPiiGate()
        assert gate.check(m, {"no_pii": True}).passed is True
        assert gate.check(m, {"no_pii": False}).passed is False

    def test_default_gates_returns_four(self):
        gates = default_gates()
        assert len(gates) == 4
        names = {g.name for g in gates}
        assert names == {"tests_green", "evidence_complete", "secret_scan_clean", "no_pii"}


# ---------------------------------------------------------------------------
# ReleasePipeline tests
# ---------------------------------------------------------------------------


class TestReleasePipeline:
    def test_create_release(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = pipeline.create_release("4.1.0", "abcdef1234567890")
        assert m.version == "4.1.0"
        assert m.sha == "abcdef1234567890"
        assert m.status == "draft"
        # Should have at least the self-integrity hash
        assert len(m.evidence_hashes) >= 1

    def test_create_release_with_real_artifact(self, tmp_path):
        # Create a fake artifact
        art = tmp_path / "build" / "app.bin"
        art.parent.mkdir(parents=True)
        art.write_bytes(b"fake binary content")
        pipeline = ReleasePipeline(repo_root=tmp_path)
        m = pipeline.create_release("1.0.0", "aaa", artifacts=["build/app.bin"])
        # Should have artifact hash + self hash
        assert len(m.evidence_hashes) == 2

    def test_verify_gates_all_pass(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = _make_manifest(evidence_hashes=["a" * 64])
        results = pipeline.verify_promotion_gates(m, _passing_context())
        assert all(r.passed for r in results)

    def test_verify_gates_partial_fail(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = _make_manifest(evidence_hashes=["a" * 64])
        ctx = _passing_context()
        ctx["secret_scan_clean"] = False
        results = pipeline.verify_promotion_gates(m, ctx)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert failed[0].gate_name == "secret_scan_clean"


class TestPromotion:
    def _ready_manifest(self) -> ReleaseManifest:
        """Manifest that will pass all gates."""
        return _make_manifest(evidence_hashes=["a" * 64])

    def test_promote_dev_to_staging(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = self._ready_manifest()
        result = pipeline.promote(m, "dev", "staging", _passing_context())
        assert result.success is True
        assert m.status == "staging"
        assert result.evidence_hash
        assert len(m.promotion_history) == 1

    def test_promote_staging_to_production(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = self._ready_manifest()
        m.status = "staging"
        result = pipeline.promote(m, "staging", "production", _passing_context())
        assert result.success is True
        assert m.status == "production"

    def test_promote_skipping_env_fails(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = self._ready_manifest()
        result = pipeline.promote(m, "dev", "production", _passing_context())
        assert result.success is False
        assert "expected" in result.detail.lower()

    def test_promote_from_production_fails(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = self._ready_manifest()
        m.status = "production"
        result = pipeline.promote(m, "production", "production", _passing_context())
        assert result.success is False

    def test_promote_gate_failure_blocks(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = self._ready_manifest()
        ctx = _passing_context()
        ctx["tests_green"] = False
        result = pipeline.promote(m, "dev", "staging", ctx)
        assert result.success is False
        assert "tests_green" in result.detail
        assert m.status == "draft"  # unchanged

    def test_promote_evidence_chain_grows(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = self._ready_manifest()
        initial_count = len(m.evidence_hashes)
        pipeline.promote(m, "dev", "staging", _passing_context())
        assert len(m.evidence_hashes) == initial_count + 1

    def test_full_promotion_path(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = self._ready_manifest()
        ctx = _passing_context()

        r1 = pipeline.promote(m, "dev", "staging", ctx)
        assert r1.success is True
        assert m.status == "staging"

        r2 = pipeline.promote(m, "staging", "production", ctx)
        assert r2.success is True
        assert m.status == "production"
        assert len(m.promotion_history) == 2


class TestRollback:
    def test_rollback_from_staging(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = _make_manifest(status="staging", evidence_hashes=["a" * 64])
        record = pipeline.rollback(m, reason="critical bug")
        assert m.status == "rolled_back"
        assert record.previous_status == "staging"
        assert record.rollback_reason == "critical bug"
        assert record.evidence_hash
        assert len(record.evidence_hash) == 64

    def test_rollback_from_production(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = _make_manifest(status="production", evidence_hashes=["a" * 64])
        record = pipeline.rollback(m)
        assert m.status == "rolled_back"
        assert record.previous_status == "production"

    def test_rollback_appends_evidence(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = _make_manifest(status="staging", evidence_hashes=["a" * 64])
        initial_count = len(m.evidence_hashes)
        pipeline.rollback(m)
        assert len(m.evidence_hashes) == initial_count + 1

    def test_rollback_appends_to_history(self):
        pipeline = ReleasePipeline(repo_root=REPO_ROOT)
        m = _make_manifest(status="staging")
        pipeline.rollback(m, reason="test")
        assert len(m.promotion_history) == 1
        assert m.promotion_history[0]["action"] == "rollback"


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_save_and_load(self, tmp_path):
        m = _make_manifest(artifacts=["a.txt"], evidence_hashes=["b" * 64])
        p = tmp_path / "release.json"
        ReleasePipeline.save_manifest(m, p)
        assert p.exists()

        loaded = ReleasePipeline.load_manifest(p)
        assert loaded.version == m.version
        assert loaded.sha == m.sha
        assert loaded.release_id == m.release_id
        assert loaded.artifacts == m.artifacts
        assert loaded.evidence_hashes == m.evidence_hashes

    def test_save_creates_dirs(self, tmp_path):
        m = _make_manifest()
        p = tmp_path / "deep" / "nested" / "release.json"
        ReleasePipeline.save_manifest(m, p)
        assert p.exists()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_create_stdout(self, capsys):
        from release_pipeline import main
        rc = main(["create", "--version", "1.0.0", "--sha", "deadbeef"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["version"] == "1.0.0"
        assert data["status"] == "draft"

    def test_create_to_file(self, tmp_path):
        from release_pipeline import main
        out_path = tmp_path / "m.json"
        rc = main(["create", "--version", "2.0.0", "--sha", "aabbcc", "--output", str(out_path)])
        assert rc == 0
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["version"] == "2.0.0"

    def test_no_command_returns_fail(self):
        from release_pipeline import main
        rc = main([])
        assert rc != 0
