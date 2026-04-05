#!/usr/bin/env python3
"""E2E tests for export verification (verify_export.py).

Test matrix:
  - test_pass_public_doc:         allowed public file => PASS
  - test_fail_private_file:       forbidden private file in bundle => FAIL
  - test_fail_hash_mismatch:      per-file SHA256 mismatch => FAIL
  - test_fail_deny_glob:          deny-glob match in included files => FAIL
  - test_fail_bundle_hash:        bundle SHA256 mismatch => FAIL
  - test_fail_extension:          disallowed extension => FAIL
  - test_fail_oversized:          file exceeds max_file_size_bytes => FAIL
  - test_fail_missing_manifest:   required fields missing => FAIL
  - test_warn_no_zip:             no ZIP provided => WARN
  - test_pass_full_bundle:        complete valid bundle => PASS
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

# Add the scripts directory to path so we can import verify_export
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "12_tooling" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from verify_export import (
    EXIT_CORRUPT,
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_WARN,
    verify_export,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_zip(zip_path: Path, file_contents: dict[str, bytes]) -> str:
    """Create a ZIP with given contents and return its SHA256."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for name, data in sorted(file_contents.items()):
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, data)
    return _sha256(zip_path.read_bytes())


def _make_manifest(
    manifest_path: Path,
    *,
    files: list[dict[str, Any]],
    excluded_files: list[dict[str, str]] | None = None,
    bundle_sha256: str = "",
    status: str = "PASS",
    deny_globs: list[str] | None = None,
    allow_prefixes: list[str] | None = None,
    allow_extensions: list[str] | None = None,
    max_file_size_bytes: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a manifest JSON and return it."""
    manifest: dict[str, Any] = {
        "schema_version": "2.0.0",
        "generated_utc": "2026-03-10T12:00:00Z",
        "status": status,
        "source_repo": "SSID",
        "source_ref": "abc1234567890",
        "target_repo": "SSID-open-core",
        "target_ref": "main",
        "policy_file": "16_codex/opencore_export_policy.yaml",
        "policy_version": "2.0.0",
        "policy_sha256": "0" * 64,
        "tool_version": "2.0.0",
        "files": files,
        "excluded_files": excluded_files or [],
        "bundle_sha256": bundle_sha256,
    }
    if deny_globs is not None:
        manifest["deny_globs"] = deny_globs
    if allow_prefixes is not None:
        manifest["allow_prefixes"] = allow_prefixes
    if allow_extensions is not None:
        manifest["allow_extensions"] = allow_extensions
    if max_file_size_bytes:
        manifest["max_file_size_bytes"] = max_file_size_bytes
    if extra:
        manifest.update(extra)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _make_policy(policy_path: Path, **overrides: Any) -> None:
    """Create a minimal policy YAML."""
    policy = {
        "schema_version": "2.0.0",
        "source_repo": "SSID",
        "target_repo": "SSID-open-core",
        "mode": "filtered",
        "allow_prefixes": ["03_core/", "12_tooling/", "16_codex/", "docs/", "README.md", "LICENSE"],
        "allow_extensions": [".py", ".yaml", ".yml", ".json", ".md", ".txt", ".sh"],
        "max_file_size_bytes": 1048576,
        "deny_globs": [
            "**/.env",
            "**/.env.*",
            "**/*.pem",
            "**/*.key",
            "**/*.secret",
            "02_audit_logging/**",
            "23_compliance/evidence/**",
            "**/worm/**",
            "**/quarantine/**",
            "**/agent_runs/**",
            "**/INTERNAL_*.md",
            "**/PRIVATE_*.md",
        ],
        "secret_scan_regex": [],
    }
    policy.update(overrides)
    policy_path.write_text(
        json.dumps(policy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# -------------------------------------------------------------------------
# TEST: allowed public doc => PASS
# -------------------------------------------------------------------------
class TestPassPublicDoc:
    def test_pass_public_doc(self, tmp_path: Path) -> None:
        content = b"# Public Documentation\nThis is public.\n"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"docs/README.md": content})

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[{"path": "docs/README.md", "sha256": file_hash, "size_bytes": len(content)}],
            bundle_sha256=bundle_hash,
            allow_prefixes=["docs/"],
            allow_extensions=[".md"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_PASS
        assert len(result.failures) == 0


# -------------------------------------------------------------------------
# TEST: forbidden private file => FAIL
# -------------------------------------------------------------------------
class TestFailPrivateFile:
    def test_fail_private_file(self, tmp_path: Path) -> None:
        content = b"private data"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"02_audit_logging/secret.log": content})

        manifest_path = tmp_path / "manifest.json"
        policy_path = tmp_path / "policy.yaml"
        _make_policy(policy_path)
        _make_manifest(
            manifest_path,
            files=[{"path": "02_audit_logging/secret.log", "sha256": file_hash, "size_bytes": len(content)}],
            bundle_sha256=bundle_hash,
        )

        result = verify_export(manifest_path, policy_path=policy_path, zip_path=zip_path)
        assert result.exit_code == EXIT_FAIL
        assert any("deny_glob" in f or "allow_prefix" in f for f in result.failures)


# -------------------------------------------------------------------------
# TEST: hash mismatch => FAIL
# -------------------------------------------------------------------------
class TestFailHashMismatch:
    def test_fail_hash_mismatch(self, tmp_path: Path) -> None:
        content = b"correct content"
        tampered = b"tampered content"
        file_hash = _sha256(content)  # hash of original
        zip_path = tmp_path / "bundle.zip"
        # ZIP contains tampered content
        bundle_hash = _make_zip(zip_path, {"docs/file.md": tampered})

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[{"path": "docs/file.md", "sha256": file_hash, "size_bytes": len(content)}],
            bundle_sha256=bundle_hash,
            allow_prefixes=["docs/"],
            allow_extensions=[".md"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_CORRUPT
        assert any("SHA256 mismatch" in c and "docs/file.md" in c for c in result.corrupt)


# -------------------------------------------------------------------------
# TEST: deny-glob match => FAIL
# -------------------------------------------------------------------------
class TestFailDenyGlob:
    def test_fail_deny_glob_match(self, tmp_path: Path) -> None:
        content = b"secret key data"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"12_tooling/config.pem": content})

        manifest_path = tmp_path / "manifest.json"
        policy_path = tmp_path / "policy.yaml"
        _make_policy(policy_path)
        _make_manifest(
            manifest_path,
            files=[{"path": "12_tooling/config.pem", "sha256": file_hash, "size_bytes": len(content)}],
            bundle_sha256=bundle_hash,
        )

        result = verify_export(manifest_path, policy_path=policy_path, zip_path=zip_path)
        assert result.exit_code == EXIT_FAIL
        assert any("deny_glob" in f for f in result.failures)


# -------------------------------------------------------------------------
# TEST: bundle SHA256 mismatch => FAIL
# -------------------------------------------------------------------------
class TestFailBundleHash:
    def test_fail_bundle_hash_mismatch(self, tmp_path: Path) -> None:
        content = b"valid content"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        _make_zip(zip_path, {"docs/file.md": content})

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[{"path": "docs/file.md", "sha256": file_hash, "size_bytes": len(content)}],
            bundle_sha256="0" * 64,  # wrong hash
            allow_prefixes=["docs/"],
            allow_extensions=[".md"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_CORRUPT
        assert any("bundle SHA256 mismatch" in c for c in result.corrupt)


# -------------------------------------------------------------------------
# TEST: disallowed extension => FAIL
# -------------------------------------------------------------------------
class TestFailExtension:
    def test_fail_disallowed_extension(self, tmp_path: Path) -> None:
        content = b"\x00\x01\x02binary"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"12_tooling/tool.exe": content})

        manifest_path = tmp_path / "manifest.json"
        policy_path = tmp_path / "policy.yaml"
        _make_policy(policy_path)
        _make_manifest(
            manifest_path,
            files=[{"path": "12_tooling/tool.exe", "sha256": file_hash, "size_bytes": len(content)}],
            bundle_sha256=bundle_hash,
        )

        result = verify_export(manifest_path, policy_path=policy_path, zip_path=zip_path)
        assert result.exit_code == EXIT_FAIL
        assert any("extension" in f.lower() or "deny_glob" in f for f in result.failures)


# -------------------------------------------------------------------------
# TEST: oversized file => FAIL
# -------------------------------------------------------------------------
class TestFailOversized:
    def test_fail_oversized_file(self, tmp_path: Path) -> None:
        content = b"x"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"docs/big.md": content})

        manifest_path = tmp_path / "manifest.json"
        policy_path = tmp_path / "policy.yaml"
        _make_policy(policy_path, max_file_size_bytes=100)
        _make_manifest(
            manifest_path,
            files=[{"path": "docs/big.md", "sha256": file_hash, "size_bytes": 200}],  # claims 200
            bundle_sha256=bundle_hash,
        )

        result = verify_export(manifest_path, policy_path=policy_path, zip_path=zip_path)
        assert result.exit_code == EXIT_FAIL
        assert any("max_file_size" in f for f in result.failures)


# -------------------------------------------------------------------------
# TEST: missing manifest fields => FAIL
# -------------------------------------------------------------------------
class TestFailMissingManifestFields:
    def test_fail_missing_fields(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.json"
        # Minimal manifest missing most required fields
        manifest_path.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "files": [],
                    "excluded_files": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = verify_export(manifest_path)
        assert result.exit_code == EXIT_FAIL
        assert any("missing required fields" in f for f in result.failures)


# -------------------------------------------------------------------------
# TEST: no ZIP => WARN (soft warning, hash checks skipped)
# -------------------------------------------------------------------------
class TestWarnNoZip:
    def test_warn_no_zip(self, tmp_path: Path) -> None:
        content = b"public content"
        file_hash = _sha256(content)
        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[{"path": "docs/file.md", "sha256": file_hash, "size_bytes": len(content)}],
            bundle_sha256="abc123",
            allow_prefixes=["docs/"],
            allow_extensions=[".md"],
        )

        result = verify_export(manifest_path, zip_path=None)
        assert result.exit_code == EXIT_WARN
        assert len(result.failures) == 0
        assert any("no ZIP bundle" in w for w in result.warnings)


# -------------------------------------------------------------------------
# TEST: complete valid bundle => PASS
# -------------------------------------------------------------------------
class TestPassFullBundle:
    def test_pass_full_bundle(self, tmp_path: Path) -> None:
        files_content = {
            "03_core/validators/check.py": b"# validator\ndef check(): pass\n",
            "12_tooling/scripts/run.sh": b"#!/bin/bash\necho ok\n",
            "16_codex/contracts/rules.yaml": b"rules:\n  - id: R001\n",
            "docs/guide.md": b"# Guide\nUsage info.\n",
            "README.md": b"# SSID Open Core\n",
        }

        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, files_content)

        manifest_files = [
            {
                "path": path,
                "sha256": _sha256(data),
                "size_bytes": len(data),
            }
            for path, data in sorted(files_content.items())
        ]

        manifest_path = tmp_path / "manifest.json"
        policy_path = tmp_path / "policy.yaml"
        _make_policy(policy_path)
        _make_manifest(
            manifest_path,
            files=manifest_files,
            bundle_sha256=bundle_hash,
        )

        result = verify_export(manifest_path, policy_path=policy_path, zip_path=zip_path)
        assert result.exit_code == EXIT_PASS
        assert len(result.failures) == 0
        assert len(result.warnings) == 0


# -------------------------------------------------------------------------
# TEST: ZIP contains file not in manifest => FAIL
# -------------------------------------------------------------------------
class TestFailExtraFileInZip:
    def test_fail_extra_file_in_zip(self, tmp_path: Path) -> None:
        content_a = b"public a"
        content_extra = b"sneaky extra"
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(
            zip_path,
            {
                "docs/a.md": content_a,
                "docs/extra.md": content_extra,
            },
        )

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[{"path": "docs/a.md", "sha256": _sha256(content_a), "size_bytes": len(content_a)}],
            bundle_sha256=bundle_hash,
            allow_prefixes=["docs/"],
            allow_extensions=[".md"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_FAIL
        assert any("not in manifest" in f for f in result.failures)


# -------------------------------------------------------------------------
# TEST: ZIP contains denied path directly => FAIL
# -------------------------------------------------------------------------
class TestFailDeniedPathInZip:
    def test_fail_denied_path_in_zip(self, tmp_path: Path) -> None:
        content = b"env secrets"
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(
            zip_path,
            {
                "docs/ok.md": b"ok",
                "12_tooling/.env": content,
            },
        )

        manifest_path = tmp_path / "manifest.json"
        policy_path = tmp_path / "policy.yaml"
        _make_policy(policy_path)
        _make_manifest(
            manifest_path,
            files=[
                {"path": "docs/ok.md", "sha256": _sha256(b"ok"), "size_bytes": 2},
                {"path": "12_tooling/.env", "sha256": _sha256(content), "size_bytes": len(content)},
            ],
            bundle_sha256=bundle_hash,
        )

        result = verify_export(manifest_path, policy_path=policy_path, zip_path=zip_path)
        assert result.exit_code == EXIT_FAIL
        assert any("deny" in f.lower() for f in result.failures)


# -------------------------------------------------------------------------
# TEST: corrupted ZIP => CORRUPT (exit code 3)
# -------------------------------------------------------------------------
class TestCorruptZip:
    def test_corrupt_zip_file(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "bundle.zip"
        zip_path.write_bytes(b"NOT A VALID ZIP FILE")

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[{"path": "docs/file.md", "sha256": "a" * 64, "size_bytes": 10}],
            bundle_sha256="b" * 64,
            allow_prefixes=["docs/"],
            allow_extensions=[".md"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_CORRUPT
        assert any("corrupted" in c.lower() or "mismatch" in c.lower() for c in result.corrupt)


# -------------------------------------------------------------------------
# TEST: invalid manifest JSON => CORRUPT (exit code 3)
# -------------------------------------------------------------------------
class TestCorruptManifest:
    def test_corrupt_manifest_json(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{invalid json!!!", encoding="utf-8")

        result = verify_export(manifest_path)
        assert result.exit_code == EXIT_CORRUPT
        assert any("cannot load manifest" in c for c in result.corrupt)


# -------------------------------------------------------------------------
# TEST: valid provenance with redacted file => PASS
# -------------------------------------------------------------------------
class TestPassProvenanceRedacted:
    def test_pass_redacted_provenance(self, tmp_path: Path) -> None:
        content = b"# Redacted module\ndef foo(): pass\n"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"03_core/module.py": content})

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[
                {
                    "path": "03_core/module.py",
                    "sha256": file_hash,
                    "size_bytes": len(content),
                    "sanitized": True,
                    "provenance": {
                        "status": "redacted",
                        "public_safe": True,
                        "sanitization_rule": "secret_redact_v1",
                        "policy_ref": "opencore_export_policy.yaml",
                    },
                }
            ],
            bundle_sha256=bundle_hash,
            allow_prefixes=["03_core/"],
            allow_extensions=[".py"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_PASS
        assert len(result.failures) == 0


# -------------------------------------------------------------------------
# TEST: sanitized=True but provenance.status != redacted => WARN
# -------------------------------------------------------------------------
class TestWarnProvenanceMismatch:
    def test_warn_sanitized_but_not_redacted(self, tmp_path: Path) -> None:
        content = b"# Some code\n"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"03_core/code.py": content})

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[
                {
                    "path": "03_core/code.py",
                    "sha256": file_hash,
                    "size_bytes": len(content),
                    "sanitized": True,
                    "provenance": {
                        "status": "unchanged",
                        "public_safe": True,
                        "sanitization_rule": None,
                        "policy_ref": "opencore_export_policy.yaml",
                    },
                }
            ],
            bundle_sha256=bundle_hash,
            allow_prefixes=["03_core/"],
            allow_extensions=[".py"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_WARN
        assert any("sanitized" in w and "redacted" in w for w in result.warnings)


# -------------------------------------------------------------------------
# TEST: invalid provenance status => FAIL
# -------------------------------------------------------------------------
class TestFailInvalidProvenanceStatus:
    def test_fail_invalid_status(self, tmp_path: Path) -> None:
        content = b"# Code\n"
        file_hash = _sha256(content)
        zip_path = tmp_path / "bundle.zip"
        bundle_hash = _make_zip(zip_path, {"03_core/mod.py": content})

        manifest_path = tmp_path / "manifest.json"
        _make_manifest(
            manifest_path,
            files=[
                {
                    "path": "03_core/mod.py",
                    "sha256": file_hash,
                    "size_bytes": len(content),
                    "sanitized": False,
                    "provenance": {
                        "status": "BOGUS_STATUS",
                        "public_safe": True,
                    },
                }
            ],
            bundle_sha256=bundle_hash,
            allow_prefixes=["03_core/"],
            allow_extensions=[".py"],
        )

        result = verify_export(manifest_path, zip_path=zip_path)
        assert result.exit_code == EXIT_FAIL
        assert any("invalid" in f and "BOGUS_STATUS" in f for f in result.failures)
