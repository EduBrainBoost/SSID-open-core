import json
import tempfile
from pathlib import Path
import pytest
from ssid_autorunner.evidence import EvidenceWriter, EvidenceEntry

def test_write_single_entry(tmp_path):
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    writer.append(EvidenceEntry(
        check="forbidden_ext",
        file_path="src/file.py",
        result="PASS",
        sha256="a" * 64,
    ))
    lines = (tmp_path / "evidence.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["check"] == "forbidden_ext"
    assert entry["result"] == "PASS"
    assert "ts" in entry

def test_append_multiple_entries(tmp_path):
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    for i in range(3):
        writer.append(EvidenceEntry(check=f"check_{i}", result="PASS"))
    lines = (tmp_path / "evidence.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3

def test_manifest_written_on_finalize(tmp_path):
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    writer.append(EvidenceEntry(check="test", result="PASS"))
    manifest = writer.finalize(status="PASS", autorunner_id="AR-07")
    assert manifest["status"] == "PASS"
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "manifest.json.sha256").exists()

def test_sha256_manifest_correct(tmp_path):
    import hashlib
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    writer.finalize(status="PASS", autorunner_id="AR-07")
    manifest_bytes = (tmp_path / "manifest.json").read_bytes()
    expected_sha = hashlib.sha256(manifest_bytes).hexdigest()
    actual_sha = (tmp_path / "manifest.json.sha256").read_text().strip()
    assert actual_sha == expected_sha

def test_finalize_twice_raises_worm_violation(tmp_path):
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    writer.finalize(status="PASS", autorunner_id="AR-07")
    with pytest.raises(FileExistsError, match="WORM violation"):
        writer.finalize(status="PASS", autorunner_id="AR-07")
