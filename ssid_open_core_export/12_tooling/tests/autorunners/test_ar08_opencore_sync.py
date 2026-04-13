import json
import subprocess
from pathlib import Path

DENY_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "apply_deny_globs.py"
SSID_ROOT = Path(__file__).parent.parent.parent.parent


def test_worm_storage_excluded(tmp_path):
    worm = tmp_path / "02_audit_logging" / "storage" / "worm"
    worm.mkdir(parents=True)
    (worm / "entry.jsonl").write_text('{"hash":"abc"}')
    allowed = tmp_path / "03_core" / "fee.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text("pass")

    r = subprocess.run(
        [
            "python",
            str(DENY_SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--deny-globs",
            "02_audit_logging/storage/worm/**",
        ],
        capture_output=True,
        text=True,
    )
    result = json.loads(r.stdout)
    sync_files = result["files_to_sync"]
    assert not any("worm" in f for f in sync_files)
    assert any("fee.py" in f for f in sync_files)


def test_evidence_excluded(tmp_path):
    ev = tmp_path / "02_audit_logging" / "evidence"
    ev.mkdir(parents=True)
    (ev / "proof.json").write_text("{}")
    r = subprocess.run(
        [
            "python",
            str(DENY_SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--deny-globs",
            "02_audit_logging/evidence/**",
        ],
        capture_output=True,
        text=True,
    )
    result = json.loads(r.stdout)
    assert not any("evidence" in f for f in result["files_to_sync"])


def test_all_deny_globs_from_policy():
    import yaml

    policy = yaml.safe_load((SSID_ROOT / "16_codex/opencore_export_policy.yaml").read_text())
    deny_globs = policy["deny_globs"]
    assert "02_audit_logging/storage/worm/**" in deny_globs
    assert "02_audit_logging/evidence/**" in deny_globs
    assert "24_meta_orchestration/registry/logs/**" in deny_globs
    assert "security/results/**" in deny_globs
