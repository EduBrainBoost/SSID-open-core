import json
import subprocess
from pathlib import Path
import pytest

SSID_ROOT = Path(__file__).parent.parent.parent.parent

def test_repo_scan_json_schema(tmp_path):
    output = tmp_path / "repo_scan.json"
    result = subprocess.run(
        ["python",
         str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
         "--repo-root", str(SSID_ROOT),
         "--commit-sha", "a" * 40,
         "--out", str(output)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text())
    assert "scan_ts" in data
    assert "commit_sha" in data
    assert "roots" in data
    assert "files" in data
    assert "forbidden_extensions_found" in data
    assert "shard_counts" in data
    assert "incident_response_plans" in data

def test_all_24_roots_in_scan(tmp_path):
    output = tmp_path / "repo_scan.json"
    subprocess.run([
        "python",
        str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
        "--repo-root", str(SSID_ROOT),
        "--commit-sha", "a" * 40,
        "--out", str(output)
    ], check=True)
    data = json.loads(output.read_text())
    root_ids = {r["id"] for r in data["roots"]}
    assert "01_ai_layer" in root_ids
    assert "24_meta_orchestration" in root_ids
    assert len(root_ids) == 24

def test_forbidden_extensions_detected(tmp_path):
    fake_nb = tmp_path / "test.ipynb"
    fake_nb.write_text('{"cells": []}')
    output = tmp_path / "repo_scan.json"
    subprocess.run([
        "python",
        str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
        "--repo-root", str(tmp_path),
        "--commit-sha", "a" * 40,
        "--out", str(output)
    ], check=True)
    data = json.loads(output.read_text())
    assert any(f.endswith(".ipynb") for f in data["forbidden_extensions_found"])

def test_incident_response_plans_all_24_roots(tmp_path):
    output = tmp_path / "repo_scan.json"
    subprocess.run([
        "python",
        str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
        "--repo-root", str(SSID_ROOT),
        "--commit-sha", "a" * 40,
        "--out", str(output)
    ], check=True)
    data = json.loads(output.read_text())
    assert len(data["incident_response_plans"]) == 24
