import json
import subprocess
from pathlib import Path

SSID_ROOT = Path(__file__).parent.parent.parent.parent
SCAN_SCRIPT = SSID_ROOT / "23_compliance" / "scripts" / "pii_regex_scan.py"
PATTERNS_FILE = SSID_ROOT / "23_compliance" / "rules" / "pii_patterns.yaml"


def _run_scan(files: list[Path], tmp_path: Path) -> tuple[int, dict]:
    out = tmp_path / "pii_results.json"
    r = subprocess.run(
        ["python", str(SCAN_SCRIPT), "--files"]
        + [str(f) for f in files]
        + ["--patterns", str(PATTERNS_FILE), "--out", str(out)],
        capture_output=True,
        text=True,
    )
    data = json.loads(out.read_text()) if out.exists() else {}
    return r.returncode, data


def test_clean_file_passes(tmp_path):
    """File with no PII returns PASS."""
    clean = tmp_path / "clean.py"
    clean.write_text(
        "def compute_hash(data: bytes) -> str:\n    import hashlib\n    return hashlib.sha256(data).hexdigest()\n"
    )
    code, data = _run_scan([clean], tmp_path)
    assert code == 0
    assert data["status"] == "PASS"
    assert data["total_findings"] == 0


def test_email_in_code_fails(tmp_path):
    """File containing a real email address fails with FAIL_POLICY."""
    dirty = tmp_path / "service.py"
    dirty.write_text('CONTACT = "alice.smith@company-internal.com"\n')
    code, data = _run_scan([dirty], tmp_path)
    assert code == 1
    assert data["status"] == "FAIL_POLICY"
    assert data["total_findings"] > 0
    assert any(f["result"] == "FAIL_POLICY" for f in data["files"])


def test_hash_only_passes(tmp_path):
    """SHA256 hex string is NOT detected as PII."""
    hash_file = tmp_path / "hashes.py"
    hash_file.write_text('KNOWN_HASH = "a3f8b2c1d9e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"\n')
    code, data = _run_scan([hash_file], tmp_path)
    assert code == 0, f"Hash-only file should PASS, got: {data}"
    assert data["status"] == "PASS"


def test_test_email_excluded(tmp_path):
    """RFC 2606 test emails (example.com) are excluded as false positives."""
    test_file = tmp_path / "test_config.py"
    test_file.write_text('EMAIL = "user@example.com"\n')
    code, data = _run_scan([test_file], tmp_path)
    assert code == 0, "test@example.com should be excluded as RFC 2606 test domain"


def test_evidence_jsonl_format(tmp_path):
    """Output JSON has required schema fields."""
    clean = tmp_path / "mod.py"
    clean.write_text("x = 1\n")
    code, data = _run_scan([clean], tmp_path)
    assert "status" in data
    assert "total_files_scanned" in data
    assert "total_findings" in data
    assert "files" in data
    assert "ts" in data


def test_patterns_file_has_all_required_types():
    """pii_patterns.yaml must include EMAIL, IBAN, PHONE patterns."""
    import yaml

    config = yaml.safe_load(PATTERNS_FILE.read_text())
    pattern_ids = {p["id"] for p in config["patterns"]}
    assert "PII_EMAIL" in pattern_ids
    assert "PII_IBAN" in pattern_ids
    assert any("PHONE" in pid for pid in pattern_ids)
