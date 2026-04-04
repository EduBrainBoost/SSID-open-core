"""Tests for 24_meta_orchestration registry files.

Covers:
  - shards_registry.json structure
  - agents_registry.json structure
  - execution_index.json structure
  - agents_manifest.json structure
  - endpoints.yaml loadability
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT_DIR / "registry"
AGENTS_DIR = ROOT_DIR / "agents" / "claude"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def shards_registry() -> dict:
    p = REGISTRY_DIR / "shards_registry.json"
    if not p.exists():
        pytest.skip("shards_registry.json not found")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def execution_index() -> dict:
    p = REGISTRY_DIR / "execution_index.json"
    if not p.exists():
        pytest.skip("execution_index.json not found")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def agents_manifest() -> dict:
    p = AGENTS_DIR / "agents_manifest.json"
    if not p.exists():
        pytest.skip("agents_manifest.json not found")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def agents_registry() -> dict:
    p = REGISTRY_DIR / "agents_registry.json"
    if not p.exists():
        pytest.skip("agents_registry.json not found")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# shards_registry.json
# ---------------------------------------------------------------------------


class TestShardsRegistry:
    def test_shards_key_present(self, shards_registry):
        assert "shards" in shards_registry, "shards_registry.json missing 'shards' key"

    def test_shards_is_list(self, shards_registry):
        assert isinstance(shards_registry["shards"], list)

    def test_each_shard_has_root_id_and_shard_id(self, shards_registry):
        for entry in shards_registry["shards"]:
            assert "root_id" in entry, f"Shard entry missing root_id: {entry}"
            assert "shard_id" in entry, f"Shard entry missing shard_id: {entry}"

    def test_all_root_ids_in_root24_lock(self, shards_registry):
        canonical = {
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
        }
        for entry in shards_registry["shards"]:
            assert entry["root_id"] in canonical, f"Shard root_id '{entry['root_id']}' not in ROOT-24-LOCK"

    def test_no_duplicate_shard_keys(self, shards_registry):
        seen: set = set()
        for entry in shards_registry["shards"]:
            key = (entry.get("root_id"), entry.get("shard_id"))
            assert key not in seen, f"Duplicate shard key: {key}"
            seen.add(key)


# ---------------------------------------------------------------------------
# execution_index.json
# ---------------------------------------------------------------------------


class TestExecutionIndex:
    def test_version_present(self, execution_index):
        assert "version" in execution_index, "execution_index.json missing 'version'"

    def test_entries_key_present(self, execution_index):
        assert "entries" in execution_index, "execution_index.json missing 'entries'"

    def test_entries_is_list(self, execution_index):
        assert isinstance(execution_index["entries"], list)

    def test_repo_field_is_ssid(self, execution_index):
        assert execution_index.get("repo") == "SSID", "execution_index.json 'repo' field should be 'SSID'"

    def test_scope_field_present_if_v2(self, execution_index):
        """scope field is present in execution_index v2.0; v1.0 may omit it."""
        version = execution_index.get("version", "")
        if str(version).startswith("2"):
            assert "scope" in execution_index, "execution_index.json v2 missing 'scope'"

    def test_each_entry_has_merge_sha(self, execution_index):
        for entry in execution_index.get("entries", []):
            assert "merge_sha" in entry, f"Entry missing merge_sha: {entry}"


# ---------------------------------------------------------------------------
# agents_manifest.json
# ---------------------------------------------------------------------------


class TestAgentsManifest:
    def test_manifest_is_dict_or_list(self, agents_manifest):
        assert isinstance(agents_manifest, (dict, list))

    def test_manifest_not_empty(self, agents_manifest):
        if isinstance(agents_manifest, dict):
            assert len(agents_manifest) > 0
        else:
            assert len(agents_manifest) > 0


# ---------------------------------------------------------------------------
# agents_registry.json
# ---------------------------------------------------------------------------


class TestAgentsRegistry:
    def test_canonical_path_present(self, agents_registry):
        assert "canonical_path" in agents_registry

    def test_count_is_positive_integer(self, agents_registry):
        assert isinstance(agents_registry.get("count"), int)
        assert agents_registry["count"] > 0

    def test_runtime_targets_is_list(self, agents_registry):
        assert isinstance(agents_registry.get("runtime_targets"), list)

    def test_manifest_field_present(self, agents_registry):
        assert "manifest" in agents_registry


# ---------------------------------------------------------------------------
# endpoints.yaml
# ---------------------------------------------------------------------------


class TestEndpointsYaml:
    def test_file_exists(self):
        assert (REGISTRY_DIR / "endpoints.yaml").exists(), "endpoints.yaml not found"

    def test_file_parseable_as_yaml(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")
        content = (REGISTRY_DIR / "endpoints.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "endpoints.yaml must parse to a dict"

    def test_has_schema_version(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")
        content = (REGISTRY_DIR / "endpoints.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert "schema_version" in data, "endpoints.yaml missing schema_version"

    def test_has_environments(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")
        content = (REGISTRY_DIR / "endpoints.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert "environments" in data, "endpoints.yaml missing environments"

    def test_no_placeholder_content(self):
        content = (REGISTRY_DIR / "endpoints.yaml").read_text(encoding="utf-8")
        assert "PLACEHOLDER" not in content.upper(), "endpoints.yaml still contains placeholder content"
