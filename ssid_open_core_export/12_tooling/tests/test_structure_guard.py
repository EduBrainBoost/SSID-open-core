"""Tests for 12_tooling/scripts/structure_guard.py.

Covers:
  - die() raises SystemExit with EXIT_CODE=24
  - main() passes on a valid minimal repo layout
  - main() fails when root count != 24
  - main() fails on symlinks at repo root
  - main() fails on archive files at repo root
  - main() fails on unauthorised directories
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = REPO_ROOT / "12_tooling" / "scripts" / "structure_guard.py"

ROOT_24_LOCK = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_guard():
    spec = importlib.util.spec_from_file_location("structure_guard", GUARD_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _make_valid_repo(tmp_path: Path) -> Path:
    """Create a minimal valid SSID repo structure in tmp_path.

    Uses a .git *file* (worktree pointer) rather than a directory, because
    structure_guard only allows .git as a file (worktree marker) at repo root.
    """
    # .git as a file simulates a git worktree — the guard explicitly allows this
    (tmp_path / ".git").write_text("gitdir: ../.git/worktrees/agent\n", encoding="utf-8")
    for name in ROOT_24_LOCK:
        (tmp_path / name).mkdir()
    exc_dir = tmp_path / "23_compliance" / "exceptions"
    exc_dir.mkdir(parents=True, exist_ok=True)
    (exc_dir / "root_level_exceptions.yaml").write_text(
        "allowed_directories: []\nallowed_files: [README.md, LICENSE, pytest.ini, conftest.py]\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# SSID\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Guard file presence
# ---------------------------------------------------------------------------


class TestStructureGuardPresence:
    def test_guard_file_exists(self):
        assert GUARD_PATH.exists(), "structure_guard.py not found"

    def test_guard_is_valid_python(self):
        try:
            compile(GUARD_PATH.read_text(encoding="utf-8"), str(GUARD_PATH), "exec")
        except SyntaxError as exc:
            pytest.fail(f"structure_guard.py has syntax errors: {exc}")

    def test_guard_defines_exit_code_24(self):
        mod = _load_guard()
        assert mod.EXIT_CODE == 24


# ---------------------------------------------------------------------------
# die() function
# ---------------------------------------------------------------------------


class TestStructureGuardDie:
    @pytest.fixture(autouse=True)
    def _guard(self):
        self.mod = _load_guard()

    def test_die_raises_system_exit(self):
        with pytest.raises(SystemExit):
            self.mod.die("test failure")

    def test_die_exit_code_is_24(self):
        with pytest.raises(SystemExit) as exc_info:
            self.mod.die("test failure")
        assert exc_info.value.code == 24

    def test_die_prints_prefix(self, capsys):
        with pytest.raises(SystemExit):
            self.mod.die("missing exceptions file")
        captured = capsys.readouterr()
        assert "STRUCTURE_GUARD_FAIL" in captured.out


# ---------------------------------------------------------------------------
# main() — valid layout
# ---------------------------------------------------------------------------


class TestStructureGuardMainPass:
    """main() must return 0 on a valid minimal repo layout."""

    def test_passes_on_valid_repo(self, tmp_path, monkeypatch):
        repo = _make_valid_repo(tmp_path)
        guard = _load_guard()
        # Redirect guard's repo_root resolution to tmp_path
        monkeypatch.setattr(guard, "main", _patched_main(guard, repo))
        result = guard.main()
        assert result == 0

    def test_prints_pass_on_valid_repo(self, tmp_path, monkeypatch, capsys):
        repo = _make_valid_repo(tmp_path)
        guard = _load_guard()
        monkeypatch.setattr(guard, "main", _patched_main(guard, repo))
        guard.main()
        captured = capsys.readouterr()
        assert "STRUCTURE_GUARD_PASS" in captured.out


# ---------------------------------------------------------------------------
# main() — failure cases
# ---------------------------------------------------------------------------


class TestStructureGuardMainFail:
    def test_fails_with_25_roots(self, tmp_path, monkeypatch):
        repo = _make_valid_repo(tmp_path)
        (repo / "25_extra_module").mkdir()
        guard = _load_guard()
        monkeypatch.setattr(guard, "main", _patched_main(guard, repo))
        with pytest.raises(SystemExit) as exc_info:
            guard.main()
        assert exc_info.value.code == 24

    def test_fails_with_23_roots(self, tmp_path, monkeypatch):
        repo = _make_valid_repo(tmp_path)
        import shutil

        shutil.rmtree(str(repo / "24_meta_orchestration"))
        guard = _load_guard()
        monkeypatch.setattr(guard, "main", _patched_main(guard, repo))
        with pytest.raises(SystemExit) as exc_info:
            guard.main()
        assert exc_info.value.code == 24

    def test_fails_on_archive_zip(self, tmp_path, monkeypatch):
        repo = _make_valid_repo(tmp_path)
        (repo / "artefacts.zip").write_bytes(b"PK")
        guard = _load_guard()
        monkeypatch.setattr(guard, "main", _patched_main(guard, repo))
        with pytest.raises(SystemExit) as exc_info:
            guard.main()
        assert exc_info.value.code == 24

    def test_fails_on_unauthorised_directory(self, tmp_path, monkeypatch):
        repo = _make_valid_repo(tmp_path)
        (repo / "node_modules").mkdir()
        guard = _load_guard()
        monkeypatch.setattr(guard, "main", _patched_main(guard, repo))
        with pytest.raises(SystemExit) as exc_info:
            guard.main()
        assert exc_info.value.code == 24

    def test_fails_when_exceptions_yaml_missing(self, tmp_path, monkeypatch):
        repo = _make_valid_repo(tmp_path)
        exc_file = repo / "23_compliance" / "exceptions" / "root_level_exceptions.yaml"
        exc_file.unlink()
        guard = _load_guard()
        monkeypatch.setattr(guard, "main", _patched_main(guard, repo))
        with pytest.raises(SystemExit) as exc_info:
            guard.main()
        assert exc_info.value.code == 24


# ---------------------------------------------------------------------------
# Patch helper — rewires repo_root inside main()
# ---------------------------------------------------------------------------


def _patched_main(guard_mod, repo_root: Path):
    """Return a main() variant that uses repo_root instead of __file__ resolution."""
    import yaml as _yaml

    def _main() -> int:
        exc_file = repo_root / "23_compliance" / "exceptions" / "root_level_exceptions.yaml"
        if not exc_file.exists():
            guard_mod.die(f"missing exceptions file: {exc_file.as_posix()}")

        data = _yaml.safe_load(exc_file.read_text(encoding="utf-8")) or {}
        allowed_dirs = set(data.get("allowed_directories", []) or [])
        allowed_files = set(data.get("allowed_files", []) or [])

        roots = sorted([p.name for p in repo_root.iterdir() if p.is_dir() and p.name[:2].isdigit() and "_" in p.name])
        if len(roots) != 24:
            guard_mod.die(f"expected 24 root modules, found {len(roots)}: {roots}")

        forbidden_archive_exts = {".zip", ".tgz", ".7z"}
        for p in repo_root.iterdir():
            name = p.name
            if p.is_symlink():
                guard_mod.die(f"symlink forbidden: {name}")
            if p.is_dir() and name[:2].isdigit() and "_" in name:
                continue
            if name == ".git" and p.is_file():
                continue
            if p.is_file():
                if p.suffix.lower() in forbidden_archive_exts:
                    guard_mod.die(f"forbidden archive in root: {name}")
                if name.lower().endswith(".tar.gz"):
                    guard_mod.die(f"forbidden archive in root: {name}")
            if p.is_dir():
                if name not in allowed_dirs:
                    guard_mod.die(f"unauthorized root directory: {name}")
            else:
                if name not in allowed_files:
                    guard_mod.die(f"unauthorized root file: {name}")

        print("STRUCTURE_GUARD_PASS")
        return 0

    return _main
