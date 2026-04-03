"""AGENT 10 — Minimal validation test for opencore_policy.yaml.

PASS/FAIL only — no scores.

SoT v4.1.0 | ROOT-24-LOCK
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(relpath: str) -> dict:
    """Load YAML from repo-relative path."""
    full = REPO_ROOT / relpath
    assert full.exists(), f"Missing: {full}"
    return yaml.safe_load(full.read_text(encoding="utf-8")) or {}


class TestOpencorePolicy:
    """Tests for opencore_policy.yaml."""

    def test_policy_exists(self) -> None:
        """Policy file must exist."""
        path = REPO_ROOT / "23_compliance" / "policies" / "opencore_policy.yaml"
        assert path.exists(), f"Missing: {path}"

    def test_policy_has_mode(self) -> None:
        """Policy must declare deny-by-default mode."""
        policy = _load_yaml("23_compliance/policies/opencore_policy.yaml")
        assert policy.get("mode") == "deny-by-default"

    def test_policy_has_extension_allowlist(self) -> None:
        """Policy must have extension_allowlist."""
        policy = _load_yaml("23_compliance/policies/opencore_policy.yaml")
        assert isinstance(policy.get("extension_allowlist"), list)
        assert len(policy["extension_allowlist"]) > 0

    def test_policy_has_extension_denylist(self) -> None:
        """Policy must have extension_denylist."""
        policy = _load_yaml("23_compliance/policies/opencore_policy.yaml")
        assert isinstance(policy.get("extension_denylist"), list)
        assert ".env" in policy["extension_denylist"]
        assert ".pem" in policy["extension_denylist"]

    def test_policy_has_forbidden_content_patterns(self) -> None:
        """Policy must have forbidden_content_patterns."""
        policy = _load_yaml("23_compliance/policies/opencore_policy.yaml")
        assert isinstance(policy.get("forbidden_content_patterns"), list)
        assert len(policy["forbidden_content_patterns"]) > 0

    def test_allowlist_exists(self) -> None:
        """Allowlist file must exist."""
        path = REPO_ROOT / "23_compliance" / "policies" / "open_core_export_allowlist.yaml"
        assert path.exists(), f"Missing: {path}"

    def test_allowlist_has_allowed_paths(self) -> None:
        """Allowlist must have allowed_paths."""
        allowlist = _load_yaml("23_compliance/policies/open_core_export_allowlist.yaml")
        assert isinstance(allowlist.get("allowed_paths"), list)
        assert len(allowlist["allowed_paths"]) > 0

    def test_denylist_excludes_secrets(self) -> None:
        """Extension denylist must include common secret extensions."""
        policy = _load_yaml("23_compliance/policies/opencore_policy.yaml")
        denylist = set(policy.get("extension_denylist", []))
        for ext in [".env", ".pem", ".key", ".secret", ".token"]:
            assert ext in denylist, f"{ext} missing from denylist"

    def test_no_overlap_between_allow_deny(self) -> None:
        """No extension should appear in both allowlist and denylist."""
        policy = _load_yaml("23_compliance/policies/opencore_policy.yaml")
        allow = set(policy.get("extension_allowlist", []))
        deny = set(policy.get("extension_denylist", []))
        overlap = allow & deny
        assert not overlap, f"Extension overlap: {overlap}"
