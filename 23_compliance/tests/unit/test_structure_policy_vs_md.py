"""Verify structure_policy.yaml is consistent with the SoT master definition.

Loads the canonical roots from structure_policy.yaml and asserts they match
the ROOT-24-LOCK list. Also validates that the referenced exceptions file
exists and that the policy YAML is well-formed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = REPO_ROOT / "23_compliance" / "policies" / "structure_policy.yaml"
MASTER_DEF_PATH = REPO_ROOT / "16_codex" / "ssid_master_definition_corrected_v1.1.1.md"

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


class TestStructurePolicyYaml:
    @pytest.fixture(autouse=True)
    def _load(self):
        assert POLICY_PATH.exists(), f"structure_policy.yaml missing at {POLICY_PATH}"
        self.data = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))

    def test_policy_has_required_roots(self):
        assert "required_roots" in self.data, "required_roots key missing"

    def test_policy_roots_match_lock(self):
        policy_roots = sorted(self.data["required_roots"])
        assert policy_roots == sorted(ROOT_24_LOCK), (
            f"Policy roots mismatch. "
            f"Missing: {set(ROOT_24_LOCK) - set(policy_roots)}. "
            f"Extra: {set(policy_roots) - set(ROOT_24_LOCK)}."
        )

    def test_policy_root_count_is_24(self):
        assert len(self.data["required_roots"]) == 24

    def test_policy_references_exceptions_file(self):
        root_level = self.data.get("root_level", {})
        exc_file = root_level.get("exceptions_file", "")
        assert exc_file, "root_level.exceptions_file not set"
        full_path = REPO_ROOT / exc_file
        assert full_path.exists(), f"Referenced exceptions file missing: {full_path}"

    def test_master_definition_exists(self):
        assert MASTER_DEF_PATH.exists(), f"SoT master definition not found at {MASTER_DEF_PATH}"


class TestStructurePolicyVsMasterDef:
    """Cross-check that every root listed in the policy appears in the master MD."""

    def test_all_roots_mentioned_in_master_def(self):
        """Check that every root's core name appears in the master definition.

        The master MD may use '04. deployment' format instead of '04_deployment',
        so we check for both the exact folder name and the dot-separated variant.
        """
        if not MASTER_DEF_PATH.exists():
            pytest.skip("Master definition file not present")
        content = MASTER_DEF_PATH.read_text(encoding="utf-8").lower()
        for root in ROOT_24_LOCK:
            # The master MD uses varying formats:
            #   '04_deployment', '04. deployment', '04. data_pipeline', etc.
            prefix, _, name = root.partition("_")
            variants = [
                root.lower(),  # 04_deployment
                f"{prefix}. {name}".lower(),  # 04. data_pipeline
                f"{prefix}. {name.replace('_', ' ')}".lower(),  # 04. data pipeline
                name.replace("_", " ").lower(),  # data pipeline
                name.replace("_", "_").lower(),  # data_pipeline
            ]
            found = any(v in content for v in variants)
            assert found, f"Root '{root}' not found in master definition. Searched variants: {variants}"
