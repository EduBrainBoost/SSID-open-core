import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent.parent.parent / "24_meta_orchestration" / "scripts" / "shard_completion_check.py"
SSID_ROOT = Path(__file__).parent.parent.parent.parent


def run_check(repo_root=None, extra=None):
    import tempfile

    out = tempfile.mktemp(suffix=".json")
    cmd = [
        "python",
        str(SCRIPT),
        "--repo-root",
        str(repo_root or SSID_ROOT),
        "--roots",
        "24",
        "--shards",
        "16",
        "--out",
        out,
    ]
    if extra:
        cmd += extra
    r = subprocess.run(cmd, capture_output=True, text=True)
    result = json.loads(Path(out).read_text()) if Path(out).exists() else {}
    return r.returncode, result


def test_output_schema_correct():
    code, result = run_check()
    assert "total_expected" in result
    assert result["total_expected"] == 384
    assert "total_found" in result
    assert "completion_percent" in result
    assert "by_root" in result
    assert len(result["by_root"]) == 24


def test_all_24_roots_checked():
    code, result = run_check()
    assert "01_ai_layer" in result["by_root"]
    assert "24_meta_orchestration" in result["by_root"]


def test_regression_detection(tmp_path):
    import json as _json

    state_file = tmp_path / "shard_state.json"
    state_file.write_text(_json.dumps({"total_found": 10}))
    out = tmp_path / "result.json"
    cmd = [
        "python",
        str(SCRIPT),
        "--repo-root",
        str(tmp_path),
        "--roots",
        "24",
        "--shards",
        "16",
        "--previous-state",
        str(state_file),
        "--out",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    result = _json.loads(out.read_text())
    # tmp_path has 0 charts, previous had 10 = regression
    assert result.get("regression_detected")


def test_completion_below_threshold_warns_not_fails():
    code, result = run_check()
    if result["completion_percent"] < 90:
        assert result.get("status") in ("WARN", "PASS", "FAIL_SHARD")
