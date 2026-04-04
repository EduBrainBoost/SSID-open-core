import json
import subprocess
from pathlib import Path

SSID_ROOT = Path(__file__).parent.parent.parent.parent
COLLECT_SCRIPT = SSID_ROOT / "02_audit_logging" / "scripts" / "collect_unanchored.py"
MERKLE_SCRIPT = SSID_ROOT / "02_audit_logging" / "scripts" / "build_merkle_tree.py"


def test_empty_queue_skips_anchoring(tmp_path):
    """No evidence files → empty queue → Merkle root is None."""
    agent_runs = tmp_path / "agent_runs"
    agent_runs.mkdir()
    state = tmp_path / "anchor_state.json"
    out_collect = tmp_path / "unanchored.json"

    r = subprocess.run(
        [
            "python",
            str(COLLECT_SCRIPT),
            "--since-last-anchor",
            str(state),
            "--agent-runs-dir",
            str(agent_runs),
            "--out",
            str(out_collect),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out_collect.read_text())
    assert data["total_unanchored"] == 0
    assert data["entries"] == []

    out_merkle = tmp_path / "merkle.json"
    r2 = subprocess.run(
        ["python", str(MERKLE_SCRIPT), "--input", str(out_collect), "--out", str(out_merkle)],
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 0, r2.stderr
    mdata = json.loads(out_merkle.read_text())
    assert mdata["empty"] is True
    assert mdata["root"] is None


def test_merkle_root_deterministic(tmp_path):
    """Same entries → same Merkle root every time."""
    agent_runs = tmp_path / "agent_runs"
    agent_runs.mkdir()
    # Create a fake run with evidence.jsonl
    run_dir = agent_runs / "run-test-abc"
    run_dir.mkdir()
    (run_dir / "evidence.jsonl").write_text('{"check":"semgrep","result":"PASS","ts":"2026-01-01T00:00:00Z"}\n')

    state = tmp_path / "anchor_state.json"
    out1 = tmp_path / "u1.json"
    out2 = tmp_path / "u2.json"

    for out in (out1, out2):
        subprocess.run(
            [
                "python",
                str(COLLECT_SCRIPT),
                "--since-last-anchor",
                str(state),
                "--agent-runs-dir",
                str(agent_runs),
                "--out",
                str(out),
            ],
            check=True,
        )

    m1 = tmp_path / "m1.json"
    m2 = tmp_path / "m2.json"
    for inp, mout in [(out1, m1), (out2, m2)]:
        subprocess.run(["python", str(MERKLE_SCRIPT), "--input", str(inp), "--out", str(mout)], check=True)

    d1 = json.loads(m1.read_text())
    d2 = json.loads(m2.read_text())
    assert d1["root"] == d2["root"], "Merkle root must be deterministic"
    assert d1["root"] is not None


def test_duplicate_anchor_guard(tmp_path):
    """Files already in anchor_state.json are NOT collected again."""
    agent_runs = tmp_path / "agent_runs"
    agent_runs.mkdir()
    run_dir = agent_runs / "run-already-anchored"
    run_dir.mkdir()
    ev = run_dir / "evidence.jsonl"
    ev.write_text('{"check":"test","result":"PASS"}\n')

    import hashlib

    file_hash = hashlib.sha256(ev.read_bytes()).hexdigest()

    state = tmp_path / "anchor_state.json"
    state.write_text(json.dumps({"anchored_hashes": [file_hash], "last_anchor_ts": "2026-01-01T00:00:00Z"}))

    out = tmp_path / "unanchored.json"
    subprocess.run(
        [
            "python",
            str(COLLECT_SCRIPT),
            "--since-last-anchor",
            str(state),
            "--agent-runs-dir",
            str(agent_runs),
            "--out",
            str(out),
        ],
        check=True,
    )
    data = json.loads(out.read_text())
    assert data["total_unanchored"] == 0, "Already-anchored entries must not be re-collected"


def test_new_entries_collected_after_anchor(tmp_path):
    """New evidence file (not in anchor_state) IS collected."""
    agent_runs = tmp_path / "agent_runs"
    agent_runs.mkdir()
    run_dir = agent_runs / "run-new-001"
    run_dir.mkdir()
    (run_dir / "evidence.jsonl").write_text('{"check":"pii","result":"PASS"}\n')

    state = tmp_path / "anchor_state.json"
    # Empty state = first run
    out = tmp_path / "unanchored.json"
    subprocess.run(
        [
            "python",
            str(COLLECT_SCRIPT),
            "--since-last-anchor",
            str(state),
            "--agent-runs-dir",
            str(agent_runs),
            "--out",
            str(out),
        ],
        check=True,
    )
    data = json.loads(out.read_text())
    assert data["total_unanchored"] == 1
    assert data["entries"][0]["run_id"] == "run-new-001"


def test_blockchain_url_flag_accepted_and_result_has_tx_hash_field(tmp_path):
    """--blockchain-url flag accepted; result JSON has tx_hash and blockchain_attempted fields."""
    # Create minimal unanchored_entries for merkle input
    collect_out = tmp_path / "collect.json"
    collect_out.write_text(
        '{"total_unanchored": 0, "entries": [], "last_anchor_ts": null, "collected_ts": "2026-01-01T00:00:00Z"}'
    )

    merkle_out = tmp_path / "merkle.json"
    subprocess.run(
        [
            "python",
            str(MERKLE_SCRIPT),
            "--input",
            str(collect_out),
            "--out",
            str(merkle_out),
            "--blockchain-url",
            "http://localhost:19999/api/anchor",  # nothing listening
        ],
        capture_output=True,
        text=True,
    )
    # May exit 0 or 1 depending on empty queue behavior
    assert merkle_out.exists(), "Output must be written"
    data = json.loads(merkle_out.read_text())
    assert "tx_hash" in data, "tx_hash field must be present (null on failure)"
    assert "blockchain_attempted" in data
    assert "dry_run" in data
