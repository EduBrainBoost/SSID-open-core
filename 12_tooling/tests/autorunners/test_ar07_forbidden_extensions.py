import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "forbidden_ext_check.py"


def run_check(files_dir, scan_all=False, extra_args=None):
    cmd = ["python", str(SCRIPT), "--extensions", ".ipynb .parquet .sqlite .db", "--repo-root", str(files_dir)]
    if scan_all:
        cmd += ["--scan-all", "true"]
    if extra_args:
        cmd += extra_args
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}


def test_clean_directory_passes(tmp_path):
    (tmp_path / "clean.py").write_text("print('hello')")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 0
    assert result["total_violations"] == 0


def test_ipynb_file_fails(tmp_path):
    (tmp_path / "notebook.ipynb").write_text('{"cells":[]}')
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1
    assert result["total_violations"] == 1
    assert any(v["ext"] == ".ipynb" for v in result["violations"])


def test_parquet_file_fails(tmp_path):
    (tmp_path / "data.parquet").write_bytes(b"PAR1")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1


def test_sqlite_file_fails(tmp_path):
    (tmp_path / "local.sqlite").write_bytes(b"SQLite")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1


def test_db_file_fails(tmp_path):
    (tmp_path / "cache.db").write_bytes(b"data")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1


def test_violation_contains_sot_rule(tmp_path):
    (tmp_path / "bad.ipynb").write_text("{}")
    code, result = run_check(tmp_path, scan_all=True)
    assert result["violations"][0]["sot_rule"] == "master_v1.1.1_§6"


def test_gitignore_excluded(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "cache.db").write_bytes(b"git internal")
    code, result = run_check(tmp_path, scan_all=True)
    assert result["total_violations"] == 0


def test_node_modules_excluded(tmp_path):
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "dep.db").write_bytes(b"node internal")
    code, result = run_check(tmp_path, scan_all=True)
    assert result["total_violations"] == 0
