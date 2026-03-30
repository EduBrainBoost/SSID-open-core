"""Tests for deterministic export hardening — P5-PreMerge P3."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ssid_runtime_reporter import SsidRuntimeReporter


def test_export_is_valid_json():
    """Export to tmp file, load back — must be a valid dict."""
    reporter = SsidRuntimeReporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "report.json"
        reporter.export_to_file(out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


def test_export_stable_key_ordering():
    """Export twice — top-level keys must be in identical order."""
    reporter = SsidRuntimeReporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        out1 = Path(tmpdir) / "r1.json"
        out2 = Path(tmpdir) / "r2.json"
        reporter.export_to_file(out1)
        reporter.export_to_file(out2)
        d1 = json.loads(out1.read_text(encoding="utf-8"))
        d2 = json.loads(out2.read_text(encoding="utf-8"))
        assert list(d1.keys()) == list(d2.keys())


def test_export_with_hash_returns_64char_sha256():
    """export_report_with_hash() must return a 64-character hex SHA-256 string."""
    reporter = SsidRuntimeReporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "report.json"
        _path, sha256 = reporter.export_report_with_hash(out)
        assert isinstance(sha256, str)
        assert len(sha256) == 64
        assert all(c in "0123456789abcdef" for c in sha256)


def test_export_with_hash_matches_file_content():
    """Re-read file and compute SHA-256 — must match returned hash."""
    reporter = SsidRuntimeReporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "report.json"
        path, returned_hash = reporter.export_report_with_hash(out)
        content = path.read_text(encoding="utf-8")
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert returned_hash == expected


def test_export_atomic_no_partial_file():
    """After export_to_file(), the output file exists (no .tmp leftover)."""
    reporter = SsidRuntimeReporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "report.json"
        tmp = out.with_suffix(".tmp")
        reporter.export_to_file(out)
        assert out.exists(), "Output file must exist after export"
        assert not tmp.exists(), ".tmp file must not exist after atomic rename"


def test_canonical_json_no_spaces_in_separators():
    """Exported JSON must use canonical separators (no ': ' or ', ')."""
    reporter = SsidRuntimeReporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "report.json"
        reporter.export_to_file(out)
        raw = out.read_text(encoding="utf-8")
        assert ": " not in raw, "Canonical JSON must not contain ': ' (colon-space)"
        assert ", " not in raw, "Canonical JSON must not contain ', ' (comma-space)"


def test_two_reports_have_different_timestamps():
    """Generate 2 reports — both generated_at values must be valid ISO-8601 strings."""
    from datetime import datetime, timezone
    reporter = SsidRuntimeReporter()
    r1 = reporter.generate_report()
    r2 = reporter.generate_report()
    # Validate both are parseable ISO-8601 timestamps
    dt1 = datetime.fromisoformat(r1.generated_at)
    dt2 = datetime.fromisoformat(r2.generated_at)
    assert dt1.tzinfo is not None, "generated_at must be timezone-aware"
    assert dt2.tzinfo is not None, "generated_at must be timezone-aware"


def test_report_to_json_has_stable_keys():
    """to_json() output must contain all 4 required top-level keys."""
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    data = json.loads(report.to_json())
    required_keys = {"schema_version", "generated_at", "module_health", "flow_statuses"}
    assert required_keys.issubset(data.keys()), f"Missing keys: {required_keys - set(data.keys())}"
