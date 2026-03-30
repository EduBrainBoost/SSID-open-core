import json
import subprocess
import tempfile
from pathlib import Path
import pytest

SCRIPT = Path(__file__).parent.parent.parent.parent / "24_meta_orchestration" / "scripts" / "sot_contract_check.py"
SSID_ROOT = Path(__file__).parent.parent.parent.parent

TMPDIR = Path(tempfile.gettempdir())
SOT_OUT_1 = TMPDIR / "sot_check_test.json"
SOT_OUT_2 = TMPDIR / "sot_check_test2.json"


def test_sot_rules_loaded():
    r = subprocess.run([
        "python", str(SCRIPT),
        "--rules", str(SSID_ROOT / "16_codex/contracts/sot/sot_contract.yaml"),
        "--repo-scan", str(SSID_ROOT / "24_meta_orchestration/registry/generated/repo_scan.json"),
        "--out", str(SOT_OUT_1),
        "--generate-scan-if-missing", "true",
        "--repo-root", str(SSID_ROOT),
    ], capture_output=True, text=True)
    # Only check schema — does it run and produce output
    assert r.returncode in (0, 1), r.stderr
    result = json.loads(SOT_OUT_1.read_text())
    assert "total_rules" in result
    assert result["total_rules"] >= 36  # SOT_AGENT_001-036


def test_sot_agent_001_dispatcher_exists():
    dispatcher = SSID_ROOT / "24_meta_orchestration" / "dispatcher"
    assert dispatcher.exists(), "24_meta_orchestration/dispatcher/ must exist"


def test_sot_rules_all_36_checked():
    # Ensure output from first test exists; if not, generate it
    if not SOT_OUT_1.exists():
        subprocess.run([
            "python", str(SCRIPT),
            "--rules", str(SSID_ROOT / "16_codex/contracts/sot/sot_contract.yaml"),
            "--repo-scan", str(SSID_ROOT / "24_meta_orchestration/registry/generated/repo_scan.json"),
            "--out", str(SOT_OUT_1),
            "--generate-scan-if-missing", "true",
            "--repo-root", str(SSID_ROOT),
        ], check=False)

    r = subprocess.run([
        "python", str(SCRIPT),
        "--rules", str(SSID_ROOT / "16_codex/contracts/sot/sot_contract.yaml"),
        "--repo-scan", str(SOT_OUT_1),
        "--out", str(SOT_OUT_2),
    ], capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    result = json.loads(SOT_OUT_2.read_text())
    assert result["total_rules"] >= 36
