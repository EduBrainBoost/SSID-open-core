#!/usr/bin/env python3
"""Unit tests for open_core_exporter.py.

PASS/FAIL + findings only — no scores.
Tests use temporary directories to avoid side-effects on the real repo.
"""

from __future__ import annotations

import hashlib
import json

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

import pytest

CLI_DIR = Path(__file__).resolve().parents[1] / "cli"
sys.path.insert(0, str(CLI_DIR))

from open_core_exporter import (  # noqa: E402
    ExportPolicy,
    _minimal_yaml_load,
    collect_source_files,
    generate_manifest,
    is_public_module,
    is_restricted_exportable,
    load_module_classification,
    run_export,
    sha256_bytes,
    sha256_file,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_source(tmp_path: Path) -> Path:
    """Create a minimal SSID-like source repo."""
    src = tmp_path / "source"
    src.mkdir()

    # Public module: 01_ai_layer
    ai = src / "01_ai_layer"
    ai.mkdir()
    (ai / "module.yaml").write_text(
        'module_id: "01_ai_layer"\nclassification: "Public Specification"\n',
        encoding="utf-8",
    )
    (ai / "README.md").write_text("# AI Layer\n", encoding="utf-8")
    (ai / "docs").mkdir()
    (ai / "docs" / "arch.md").write_text("Architecture\n", encoding="utf-8")
    (ai / "src").mkdir()
    (ai / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")

    # Internal module: 03_core
    core = src / "03_core"
    core.mkdir()
    (core / "module.yaml").write_text(
        'module_id: "03_core"\nclassification: "Internal Authority"\n',
        encoding="utf-8",
    )
    (core / "README.md").write_text("# Core\n", encoding="utf-8")
    (core / "docs").mkdir()
    (core / "docs" / "arch.md").write_text("Core architecture\n", encoding="utf-8")
    (core / "contracts").mkdir()
    (core / "contracts" / "api.yaml").write_text("api: v1\n", encoding="utf-8")
    (core / "interfaces").mkdir()
    (core / "interfaces" / "bus.jsonl").write_text("{}\n", encoding="utf-8")
    (core / "src").mkdir()
    (core / "src" / "validator.py").write_text("# internal implementation\n", encoding="utf-8")

    # A non-allowed root: 02_audit_logging (denied by policy deny_globs)
    audit = src / "02_audit_logging"
    audit.mkdir()
    (audit / "module.yaml").write_text(
        'module_id: "02_audit_logging"\nclassification: "Internal Governance"\n',
        encoding="utf-8",
    )
    (audit / "README.md").write_text("# Audit\n", encoding="utf-8")

    return src


@pytest.fixture()
def tmp_target(tmp_path: Path) -> Path:
    """Create an empty target directory."""
    tgt = tmp_path / "target"
    tgt.mkdir()
    return tgt


@pytest.fixture()
def policy_file(tmp_path: Path) -> Path:
    """Create a minimal export policy file."""
    pol = tmp_path / "policy.yaml"
    # Build policy data as dict and dump via json-compatible YAML
    # to avoid regex escaping issues in raw YAML strings.
    import yaml as _yaml

    policy_data = {
        "schema_version": "2.0.0",
        "source_repo": "SSID",
        "target_repo": "SSID-open-core",
        "mode": "filtered",
        "allow_prefixes": [
            "01_ai_layer/",
            "03_core/",
            "docs/",
            "README.md",
        ],
        "allow_extensions": [
            ".py",
            ".yaml",
            ".yml",
            ".md",
            ".json",
            ".jsonl",
            ".txt",
        ],
        "max_file_size_bytes": 1048576,
        "deny_globs": [
            "**/.env",
            "**/*.pem",
            "**/__pycache__/**",
            "02_audit_logging/**",
        ],
        "secret_scan_regex": [
            r"(?i)(api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            r"-----BEGIN (RSA )?PRIVATE KEY-----",
        ],
    }
    pol.write_text(_yaml.dump(policy_data, default_flow_style=False), encoding="utf-8")
    return pol


@pytest.fixture()
def policy(policy_file: Path) -> ExportPolicy:
    return ExportPolicy(policy_file)


# ---------------------------------------------------------------------------
# Tests: YAML loading
# ---------------------------------------------------------------------------


class TestMinimalYamlLoad:
    def test_flat_key_value(self) -> None:
        data = _minimal_yaml_load('key: "value"\nother: 42')
        assert data["key"] == "value"
        assert data["other"] == "42"

    def test_list_values(self) -> None:
        text = "items:\n  - one\n  - two\n  - three"
        data = _minimal_yaml_load(text)
        assert data["items"] == ["one", "two", "three"]

    def test_comments_ignored(self) -> None:
        text = "# comment\nkey: val\n# another"
        data = _minimal_yaml_load(text)
        assert data["key"] == "val"
        assert len(data) == 1


# ---------------------------------------------------------------------------
# Tests: ExportPolicy
# ---------------------------------------------------------------------------


class TestExportPolicy:
    def test_prefix_allowed(self, policy: ExportPolicy) -> None:
        assert policy.is_prefix_allowed("03_core/README.md")
        assert policy.is_prefix_allowed("01_ai_layer/src/main.py")
        assert not policy.is_prefix_allowed("02_audit_logging/README.md")

    def test_extension_allowed(self, policy: ExportPolicy) -> None:
        assert policy.is_extension_allowed("foo.py")
        assert policy.is_extension_allowed("bar.yaml")
        assert not policy.is_extension_allowed("binary.exe")
        assert not policy.is_extension_allowed("noext")

    def test_deny_glob_match(self, policy: ExportPolicy) -> None:
        assert policy.matches_deny_glob("some/.env") is not None
        assert policy.matches_deny_glob("some/file.pem") is not None
        assert policy.matches_deny_glob("02_audit_logging/data.yaml") is not None
        assert policy.matches_deny_glob("01_ai_layer/src/main.py") is None

    def test_secret_scan_clean(self, policy: ExportPolicy) -> None:
        assert policy.scan_secrets("def hello(): pass") == []

    def test_secret_scan_detects(self, policy: ExportPolicy) -> None:
        content = 'api_key = "supersecretkey123456"'  # ssid:test-fixture
        hits = policy.scan_secrets(content)
        assert len(hits) >= 1

    def test_private_key_detected(self, policy: ExportPolicy) -> None:
        content = "-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----"
        hits = policy.scan_secrets(content)
        assert len(hits) >= 1


# ---------------------------------------------------------------------------
# Tests: Classification
# ---------------------------------------------------------------------------


class TestClassification:
    def test_public_classification(self, tmp_source: Path) -> None:
        cls = load_module_classification(tmp_source / "01_ai_layer")
        assert cls == "Public Specification"
        assert is_public_module(cls)

    def test_internal_classification(self, tmp_source: Path) -> None:
        cls = load_module_classification(tmp_source / "03_core")
        assert cls == "Internal Authority"
        assert not is_public_module(cls)

    def test_missing_module_yaml(self, tmp_path: Path) -> None:
        cls = load_module_classification(tmp_path / "nonexistent")
        assert cls == "Unknown"


# ---------------------------------------------------------------------------
# Tests: Restricted export filtering
# ---------------------------------------------------------------------------


class TestRestrictedExport:
    def test_module_yaml_allowed(self) -> None:
        assert is_restricted_exportable("03_core/module.yaml")

    def test_readme_allowed(self) -> None:
        assert is_restricted_exportable("03_core/README.md")

    def test_docs_subdir_allowed(self) -> None:
        assert is_restricted_exportable("03_core/docs/arch.md")

    def test_contracts_allowed(self) -> None:
        assert is_restricted_exportable("03_core/contracts/api.yaml")

    def test_interfaces_allowed(self) -> None:
        assert is_restricted_exportable("03_core/interfaces/bus.jsonl")

    def test_src_denied(self) -> None:
        assert not is_restricted_exportable("03_core/src/validator.py")

    def test_tests_denied(self) -> None:
        assert not is_restricted_exportable("03_core/tests/test_core.py")


# ---------------------------------------------------------------------------
# Tests: SHA256 utilities
# ---------------------------------------------------------------------------


class TestSHA256:
    def test_sha256_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert sha256_file(f) == expected

    def test_sha256_bytes(self) -> None:
        expected = hashlib.sha256(b"data").hexdigest()
        assert sha256_bytes(b"data") == expected


# ---------------------------------------------------------------------------
# Tests: Full export pipeline
# ---------------------------------------------------------------------------


class TestRunExport:
    def test_dry_run_no_files_written(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        # Target should remain empty
        target_files = list(tmp_target.rglob("*"))
        assert len(target_files) == 0
        # But we should have exported entries
        assert len(result.exported) > 0

    def test_public_module_full_export(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        exported_paths = {e["path"] for e in result.exported}
        # Public module: all files should be exported
        assert "01_ai_layer/module.yaml" in exported_paths
        assert "01_ai_layer/README.md" in exported_paths
        assert "01_ai_layer/docs/arch.md" in exported_paths
        assert "01_ai_layer/src/main.py" in exported_paths

    def test_internal_module_restricted_export(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        exported_paths = {e["path"] for e in result.exported}
        excluded_paths = {e["path"] for e in result.excluded}

        # Internal module: docs, contracts, interfaces, module.yaml, README allowed
        assert "03_core/module.yaml" in exported_paths
        assert "03_core/README.md" in exported_paths
        assert "03_core/docs/arch.md" in exported_paths
        assert "03_core/contracts/api.yaml" in exported_paths
        assert "03_core/interfaces/bus.jsonl" in exported_paths

        # Internal implementation must be excluded
        assert "03_core/src/validator.py" in excluded_paths

    def test_actual_export_writes_files(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=False)
        for entry in result.exported:
            target_file = tmp_target / entry["path"]
            assert target_file.is_file(), f"Expected {entry['path']} in target"
            # Verify hash integrity
            assert sha256_file(target_file) == entry["sha256"]

    def test_secret_file_excluded(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        # Add a file with a secret to the public module
        secret_file = tmp_source / "01_ai_layer" / "src" / "config.py"
        secret_file.write_text(
            'api_key = "this_is_a_very_secret_key_value"\n',
            encoding="utf-8",  # ssid:test-fixture
        )
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        excluded_paths = {e["path"] for e in result.excluded}
        assert "01_ai_layer/src/config.py" in excluded_paths
        assert result.status == "FAIL"

    def test_oversized_file_excluded(self, tmp_source: Path, tmp_target: Path, policy_file: Path) -> None:
        # Create policy with tiny max size
        tiny_policy_text = policy_file.read_text(encoding="utf-8").replace(
            "max_file_size_bytes: 1048576", "max_file_size_bytes: 10"
        )
        tiny_pol = policy_file.parent / "tiny_policy.yaml"
        tiny_pol.write_text(tiny_policy_text, encoding="utf-8")
        tiny_policy = ExportPolicy(tiny_pol)

        result = run_export(tmp_source, tmp_target, tiny_policy, dry_run=True)
        oversized = [e for e in result.excluded if e["reason"] == "oversized"]
        assert len(oversized) > 0

    def test_denied_prefix_excluded(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        excluded_reasons = {e["path"]: e["reason"] for e in result.excluded if e["path"].startswith("02_audit_logging")}
        # Either not_in_allow_prefix or deny_glob should catch audit files
        assert len(excluded_reasons) > 0


# ---------------------------------------------------------------------------
# Tests: Manifest generation
# ---------------------------------------------------------------------------


class TestManifest:
    def test_manifest_has_required_fields(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        manifest = generate_manifest(result, policy, source_ref="abc123")

        required = [
            "schema_version",
            "generated_utc",
            "status",
            "source_repo",
            "source_ref",
            "target_repo",
            "target_ref",
            "policy_file",
            "policy_version",
            "policy_sha256",
            "tool_version",
            "files",
            "excluded_files",
            "bundle_sha256",
        ]
        for field in required:
            assert field in manifest, f"Missing required field: {field}"

    def test_manifest_file_entries_have_required_fields(
        self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy
    ) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        manifest = generate_manifest(result, policy)
        for entry in manifest["files"]:
            assert "path" in entry
            assert "sha256" in entry
            assert "size_bytes" in entry

    def test_manifest_excluded_entries_have_required_fields(
        self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy
    ) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        manifest = generate_manifest(result, policy)
        for entry in manifest["excluded_files"]:
            assert "path" in entry
            assert "reason" in entry

    def test_bundle_sha256_deterministic(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result1 = run_export(tmp_source, tmp_target, policy, dry_run=True)
        m1 = generate_manifest(result1, policy)
        result2 = run_export(tmp_source, tmp_target, policy, dry_run=True)
        m2 = generate_manifest(result2, policy)
        assert m1["bundle_sha256"] == m2["bundle_sha256"]

    def test_manifest_json_serializable(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        manifest = generate_manifest(result, policy)
        # Must be JSON-serializable without errors
        output = json.dumps(manifest, indent=2)
        assert len(output) > 0

    def test_manifest_status_pass_when_clean(self, tmp_source: Path, tmp_target: Path, policy: ExportPolicy) -> None:
        result = run_export(tmp_source, tmp_target, policy, dry_run=True)
        manifest = generate_manifest(result, policy)
        assert manifest["status"] == "PASS"


# ---------------------------------------------------------------------------
# Tests: collect_source_files
# ---------------------------------------------------------------------------


class TestCollectFiles:
    def test_excludes_git_dir(self, tmp_path: Path) -> None:
        src = tmp_path / "repo"
        src.mkdir()
        (src / ".git").mkdir()
        (src / ".git" / "config").write_text("gitconfig", encoding="utf-8")
        (src / "file.txt").write_text("content", encoding="utf-8")
        files = collect_source_files(src)
        paths = [f.name for f in files]
        assert "file.txt" in paths
        assert "config" not in paths

    def test_returns_sorted(self, tmp_path: Path) -> None:
        src = tmp_path / "repo"
        src.mkdir()
        (src / "b.txt").write_text("b", encoding="utf-8")
        (src / "a.txt").write_text("a", encoding="utf-8")
        files = collect_source_files(src)
        assert files[0].name == "a.txt"
        assert files[1].name == "b.txt"
