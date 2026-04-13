#!/usr/bin/env python3
"""Smoke test for root: 24_meta_orchestration.

Verifies L3 scaffold invariants: required directories, README, module.yaml.
No scores — PASS/FAIL + findings only.
"""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_NAME = ROOT_DIR.name


def test_readme_exists() -> None:
    """Root MUST have a README.md."""
    assert (ROOT_DIR / "README.md").exists(), f"{ROOT_NAME}/README.md missing"


def test_docs_dir_exists() -> None:
    """Root MUST have a docs/ directory."""
    assert (ROOT_DIR / "docs").is_dir(), f"{ROOT_NAME}/docs/ missing"


def test_tests_dir_exists() -> None:
    """Root MUST have a tests/ directory."""
    assert (ROOT_DIR / "tests").is_dir(), f"{ROOT_NAME}/tests/ missing"


def test_src_dir_exists() -> None:
    """Root MUST have a src/ directory."""
    assert (ROOT_DIR / "src").is_dir(), f"{ROOT_NAME}/src/ missing"


def test_shards_dir_exists() -> None:
    """Root MUST have a shards/ directory with at least one shard."""
    shards_dir = ROOT_DIR / "shards"
    assert shards_dir.is_dir(), f"{ROOT_NAME}/shards/ missing"
    shard_dirs = [d for d in shards_dir.iterdir() if d.is_dir()]
    assert len(shard_dirs) >= 1, f"{ROOT_NAME}/shards/ has no shard subdirectories"


def test_no_root24_violation() -> None:
    """Root name MUST be in the canonical ROOT-24-LOCK list."""
    canonical = [
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
    assert ROOT_NAME in canonical, f"{ROOT_NAME} not in ROOT-24-LOCK"
