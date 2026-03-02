"""Tests for build_release_bundle.py and verify_release_bundle.py."""

import json
import os
import zipfile
from pathlib import Path

import pytest

# Adjust import path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build_release_bundle import build_bundle, is_denied, sha256_file, sha256_bytes
from verify_release_bundle import verify_bundle


# --- Fixtures ---

@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a minimal public_export/ structure."""
    src = tmp_path / "public_export"
    src.mkdir()
    (src / "manifest.json").write_text(
        json.dumps({"version": "test", "files": ["a.md"]}, indent=2),
        encoding="utf-8",
    )
    (src / "a.md").write_text("# Test\n\nContent here.\n", encoding="utf-8")

    sub = src / "subdir"
    sub.mkdir()
    (sub / "b.txt").write_text("nested file\n", encoding="utf-8")
    return src


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "output"
    d.mkdir()
    return d


# --- is_denied ---

class TestIsDenied:
    def test_env_file(self):
        assert is_denied(Path(".env"))

    def test_secret_file(self):
        assert is_denied(Path("config/.secret"))

    def test_pycache(self):
        assert is_denied(Path("__pycache__/module.cpython-312.pyc"))

    def test_node_modules(self):
        assert is_denied(Path("node_modules/pkg/index.js"))

    def test_normal_file(self):
        assert not is_denied(Path("manifest.json"))

    def test_markdown(self):
        assert not is_denied(Path("docs/readme.md"))


# --- build_bundle ---

class TestBuildBundle:
    def test_creates_zip_and_sums(self, source_dir: Path, output_dir: Path):
        zip_path, sums_path = build_bundle(source_dir, output_dir)
        assert zip_path.exists()
        assert sums_path.exists()
        assert zip_path.suffix == ".zip"
        assert sums_path.name == "SHA256SUMS"

    def test_zip_contains_all_files(self, source_dir: Path, output_dir: Path):
        zip_path, _ = build_bundle(source_dir, output_dir)
        with zipfile.ZipFile(zip_path) as zf:
            names = sorted(zf.namelist())
        assert names == ["a.md", "manifest.json", "subdir/b.txt"]

    def test_sha256sums_has_zip_entry(self, source_dir: Path, output_dir: Path):
        zip_path, sums_path = build_bundle(source_dir, output_dir)
        content = sums_path.read_text(encoding="utf-8")
        assert zip_path.name in content

    def test_sha256sums_has_source_entries(self, source_dir: Path, output_dir: Path):
        _, sums_path = build_bundle(source_dir, output_dir)
        content = sums_path.read_text(encoding="utf-8")
        assert "source/manifest.json" in content
        assert "source/a.md" in content
        assert "source/subdir/b.txt" in content

    def test_deterministic_output(self, source_dir: Path, tmp_path: Path):
        """Two builds produce identical ZIP hashes."""
        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        out1.mkdir()
        out2.mkdir()

        zip1, _ = build_bundle(source_dir, out1)
        zip2, _ = build_bundle(source_dir, out2)

        assert sha256_file(zip1) == sha256_file(zip2)

    def test_denied_files_excluded(self, source_dir: Path, output_dir: Path):
        (source_dir / ".env").write_text("SECRET=bad")
        (source_dir / "__pycache__").mkdir()
        (source_dir / "__pycache__" / "mod.pyc").write_bytes(b"\x00")

        zip_path, _ = build_bundle(source_dir, output_dir)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert ".env" not in names
        assert "__pycache__/mod.pyc" not in names

    def test_empty_source_fails(self, tmp_path: Path, output_dir: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(SystemExit):
            build_bundle(empty, output_dir)

    def test_fixed_timestamps_in_zip(self, source_dir: Path, output_dir: Path):
        zip_path, _ = build_bundle(source_dir, output_dir)
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                assert info.date_time == (2026, 1, 1, 0, 0, 0)


# --- verify_bundle ---

class TestVerifyBundle:
    def test_valid_bundle_passes(self, source_dir: Path, output_dir: Path):
        zip_path, sums_path = build_bundle(source_dir, output_dir)
        assert verify_bundle(zip_path, sums_path) is True

    def test_corrupted_zip_fails(self, source_dir: Path, output_dir: Path):
        zip_path, sums_path = build_bundle(source_dir, output_dir)
        # Corrupt the ZIP
        data = zip_path.read_bytes()
        zip_path.write_bytes(data[:100] + b"\x00" * 50 + data[150:])
        assert verify_bundle(zip_path, sums_path) is False

    def test_missing_zip_fails(self, tmp_path: Path):
        sums = tmp_path / "SHA256SUMS"
        sums.write_text("abc  test.zip\n")
        assert verify_bundle(tmp_path / "nonexistent.zip", sums) is False

    def test_missing_sums_fails(self, source_dir: Path, output_dir: Path):
        zip_path, _ = build_bundle(source_dir, output_dir)
        assert verify_bundle(zip_path, output_dir / "nonexistent") is False

    def test_tampered_sums_fails(self, source_dir: Path, output_dir: Path):
        zip_path, sums_path = build_bundle(source_dir, output_dir)
        # Replace first hash with a wrong one
        content = sums_path.read_text(encoding="utf-8")
        lines = content.strip().splitlines()
        lines[0] = "0" * 64 + "  " + lines[0].split("  ", 1)[1]
        sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert verify_bundle(zip_path, sums_path) is False


# --- sha256 helpers ---

class TestSha256Helpers:
    def test_sha256_file(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello\n")
        h = sha256_file(f)
        assert len(h) == 64
        assert h == sha256_bytes(b"hello\n")

    def test_sha256_bytes_deterministic(self):
        assert sha256_bytes(b"test") == sha256_bytes(b"test")
        assert sha256_bytes(b"a") != sha256_bytes(b"b")
