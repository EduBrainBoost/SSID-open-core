#!/usr/bin/env python3
"""Compliance mapping validation tests for 23_compliance/frameworks/.

Validates:
  - Each framework YAML file is loadable (valid YAML syntax)
  - Required top-level fields are present in each mapping file
  - 'final_authority' references an existing SSID root
  - 'version' field is present and non-empty
  - 'framework_id' is lowercase alphanumeric with optional underscores/hyphens
  - GDPR mapping contains at least one article entry
  - ISO 27001 mapping contains annex_a_mappings entries
  - eIDAS mapping contains identification_schemes entries
  - MiCA mapping contains articles entries
  - All 'root' references inside ssid_roots point to canonical SSID roots

Each test is runnable standalone (pytest 23_compliance/tests/test_compliance_mapping.py).

SoT v4.1.0 | ROOT-24-LOCK
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

FRAMEWORKS_DIR = Path(__file__).resolve().parents[1] / "frameworks"
SSID_ROOT = Path(__file__).resolve().parents[2]

# Import canonical roots from 03_core/constants.py (Single Source of Truth)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("core_constants", SSID_ROOT / "03_core" / "constants.py")
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CANONICAL_ROOTS = _mod.CANONICAL_ROOTS  # frozenset

# Mapping YAML files that contain framework_id + final_authority fields.
MAPPING_FILES = [
    FRAMEWORKS_DIR / "gdpr" / "gdpr_mapping.yaml",
    FRAMEWORKS_DIR / "gdpr" / "gdpr_controls.yaml",
    FRAMEWORKS_DIR / "iso27001" / "iso27001_mapping.yaml",
    FRAMEWORKS_DIR / "eidas" / "eidas_mapping.yaml",
    FRAMEWORKS_DIR / "mica" / "mica_mapping.yaml",
    FRAMEWORKS_DIR / "mica" / "mica_controls.yaml",
]

_FRAMEWORK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return the parsed dict."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _collect_ssid_roots_from_list(entries: list[dict]) -> list[str]:
    """Extract all root names from a list of objects that have ssid_roots."""
    roots: list[str] = []
    for entry in entries:
        for r in entry.get("ssid_roots", []):
            if isinstance(r, dict) and "root" in r:
                roots.append(r["root"])
    return roots


# ---------------------------------------------------------------------------
# Test 1: All mapping YAML files are loadable (valid YAML)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("yaml_path", MAPPING_FILES, ids=[p.name for p in MAPPING_FILES])
def test_yaml_file_is_loadable(yaml_path: Path) -> None:
    """Each mapping YAML file must be parseable without errors."""
    assert yaml_path.exists(), f"Mapping file not found: {yaml_path}"
    data = _load_yaml(yaml_path)
    assert isinstance(data, dict), f"{yaml_path.name} did not parse as a dict"


# ---------------------------------------------------------------------------
# Test 2: Required top-level fields are present
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("yaml_path", MAPPING_FILES, ids=[p.name for p in MAPPING_FILES])
def test_required_top_level_fields(yaml_path: Path) -> None:
    """Each mapping YAML must have 'framework_id', 'version', and 'final_authority'."""
    data = _load_yaml(yaml_path)
    for field in ("framework_id", "version", "final_authority"):
        assert field in data, f"{yaml_path.name} missing required field: '{field}'"
        assert data[field], f"{yaml_path.name} field '{field}' must not be empty"


# ---------------------------------------------------------------------------
# Test 3: final_authority references a canonical SSID root
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("yaml_path", MAPPING_FILES, ids=[p.name for p in MAPPING_FILES])
def test_final_authority_is_canonical_root(yaml_path: Path) -> None:
    """The 'final_authority' must be one of the 24 canonical SSID roots."""
    data = _load_yaml(yaml_path)
    authority = data.get("final_authority", "")
    assert authority in CANONICAL_ROOTS, (
        f"{yaml_path.name}: final_authority '{authority}' is not a canonical SSID root"
    )


# ---------------------------------------------------------------------------
# Test 4: framework_id format is valid
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("yaml_path", MAPPING_FILES, ids=[p.name for p in MAPPING_FILES])
def test_framework_id_format(yaml_path: Path) -> None:
    """framework_id must be lowercase alphanumeric with optional underscores/hyphens."""
    data = _load_yaml(yaml_path)
    fid = data.get("framework_id", "")
    assert _FRAMEWORK_ID_RE.match(fid), (
        f"{yaml_path.name}: framework_id '{fid}' does not match pattern [a-z0-9][a-z0-9_-]*"
    )


# ---------------------------------------------------------------------------
# Test 5: GDPR mapping has article entries
# ---------------------------------------------------------------------------

def test_gdpr_mapping_has_articles() -> None:
    """gdpr_mapping.yaml must contain at least one article entry."""
    gdpr_path = FRAMEWORKS_DIR / "gdpr" / "gdpr_mapping.yaml"
    data = _load_yaml(gdpr_path)
    articles = data.get("articles", [])
    assert isinstance(articles, list) and len(articles) >= 1, (
        "gdpr_mapping.yaml must have at least one entry in 'articles'"
    )


# ---------------------------------------------------------------------------
# Test 6: GDPR controls have control_id and implementation_root
# ---------------------------------------------------------------------------

def test_gdpr_controls_have_required_fields() -> None:
    """Each GDPR control must have control_id and implementation_root."""
    controls_path = FRAMEWORKS_DIR / "gdpr" / "gdpr_controls.yaml"
    data = _load_yaml(controls_path)
    controls = data.get("controls", [])
    assert len(controls) >= 1, "gdpr_controls.yaml must have at least one control"
    for ctrl in controls:
        assert "control_id" in ctrl, f"Control missing 'control_id': {ctrl}"
        assert "implementation_root" in ctrl, f"Control {ctrl.get('control_id')} missing 'implementation_root'"
        assert ctrl["implementation_root"] in CANONICAL_ROOTS, (
            f"Control {ctrl['control_id']}: implementation_root '{ctrl['implementation_root']}' "
            f"is not a canonical root"
        )


# ---------------------------------------------------------------------------
# Test 7: ISO 27001 mapping has annex_a_mappings entries
# ---------------------------------------------------------------------------

def test_iso27001_has_annex_a_mappings() -> None:
    """iso27001_mapping.yaml must have at least one annex_a_mappings entry."""
    iso_path = FRAMEWORKS_DIR / "iso27001" / "iso27001_mapping.yaml"
    data = _load_yaml(iso_path)
    mappings = data.get("annex_a_mappings", [])
    assert isinstance(mappings, list) and len(mappings) >= 1, (
        "iso27001_mapping.yaml must have at least one entry in 'annex_a_mappings'"
    )


# ---------------------------------------------------------------------------
# Test 8: eIDAS mapping has identification_schemes
# ---------------------------------------------------------------------------

def test_eidas_has_identification_schemes() -> None:
    """eidas_mapping.yaml must have at least one identification_schemes entry."""
    eidas_path = FRAMEWORKS_DIR / "eidas" / "eidas_mapping.yaml"
    data = _load_yaml(eidas_path)
    schemes = data.get("identification_schemes", [])
    assert isinstance(schemes, list) and len(schemes) >= 1, (
        "eidas_mapping.yaml must have at least one entry in 'identification_schemes'"
    )


# ---------------------------------------------------------------------------
# Test 9: MiCA mapping has articles
# ---------------------------------------------------------------------------

def test_mica_has_articles() -> None:
    """mica_mapping.yaml must have at least one articles entry."""
    mica_path = FRAMEWORKS_DIR / "mica" / "mica_mapping.yaml"
    data = _load_yaml(mica_path)
    articles = data.get("articles", [])
    assert isinstance(articles, list) and len(articles) >= 1, (
        "mica_mapping.yaml must have at least one entry in 'articles'"
    )


# ---------------------------------------------------------------------------
# Test 10: All ssid_roots references in GDPR articles point to canonical roots
# ---------------------------------------------------------------------------

def test_gdpr_ssid_roots_are_canonical() -> None:
    """All root references inside GDPR article ssid_roots must be canonical SSID roots."""
    gdpr_path = FRAMEWORKS_DIR / "gdpr" / "gdpr_mapping.yaml"
    data = _load_yaml(gdpr_path)
    articles = data.get("articles", [])
    referenced_roots = _collect_ssid_roots_from_list(articles)

    assert len(referenced_roots) > 0, "GDPR mapping should reference at least one SSID root"

    invalid = [r for r in referenced_roots if r not in CANONICAL_ROOTS]
    assert not invalid, (
        f"GDPR mapping references non-canonical roots: {invalid}"
    )
