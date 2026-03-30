"""test_contract_freeze.py — Contract Freeze: JSON-Schema + Golden Files + Backward-Compat tests.

P1 pre-merge validation: ensures the SsidRuntimeReport schema and golden files
remain stable and backward-compatible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Locate the schema directory relative to this test file
_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"

# Ensure the 03_core package is importable
_CORE_DIR = Path(__file__).resolve().parents[1]
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(filename: str) -> dict:
    path = _SCHEMA_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_schema_json_is_valid_json():
    """Schema file must be loadable as valid JSON."""
    data = _load_json("ssid_runtime_report.schema.json")
    assert isinstance(data, dict)


def test_schema_has_required_properties():
    """Schema must declare the four top-level required properties."""
    schema = _load_json("ssid_runtime_report.schema.json")
    required = schema.get("required", [])
    for prop in ("schema_version", "generated_at", "module_health", "flow_statuses"):
        assert prop in required, f"Missing required property: {prop}"


def test_golden_healthy_is_valid_json():
    """golden_healthy.json must be loadable as valid JSON."""
    data = _load_json("golden_healthy.json")
    assert isinstance(data, dict)


def test_golden_denied_is_valid_json():
    """golden_denied.json must be loadable as valid JSON."""
    data = _load_json("golden_denied.json")
    assert isinstance(data, dict)


def test_golden_degraded_is_valid_json():
    """golden_degraded.json must be loadable as valid JSON."""
    data = _load_json("golden_degraded.json")
    assert isinstance(data, dict)


def test_golden_healthy_has_8_modules():
    """golden_healthy.json must have exactly 8 module_health entries."""
    data = _load_json("golden_healthy.json")
    assert len(data["module_health"]) == 8


def test_golden_healthy_all_modules_healthy():
    """All module_health entries in golden_healthy.json must have status 'healthy'."""
    data = _load_json("golden_healthy.json")
    for entry in data["module_health"]:
        assert entry["status"] == "healthy", (
            f"Module {entry['module_name']} has status {entry['status']!r}, expected 'healthy'"
        )


def test_golden_denied_has_deny_flow():
    """golden_denied.json must contain at least one flow with allow_or_deny=='deny' or status=='denied'."""
    data = _load_json("golden_denied.json")
    has_deny = any(
        flow.get("allow_or_deny") == "deny" or flow.get("status") == "denied"
        for flow in data["flow_statuses"]
    )
    assert has_deny, "golden_denied.json has no denied flow"


def test_schema_version_unchanged():
    """Schema title must remain 'SsidRuntimeReport' (backward-compat guard)."""
    schema = _load_json("ssid_runtime_report.schema.json")
    assert schema.get("title") == "SsidRuntimeReport"


def test_ems_contract_schema_version_matches_1_0_0():
    """SCHEMA_VERSION in ems_contract.py must be '1.0.0'."""
    from ems_contract import SCHEMA_VERSION
    assert SCHEMA_VERSION == "1.0.0"
