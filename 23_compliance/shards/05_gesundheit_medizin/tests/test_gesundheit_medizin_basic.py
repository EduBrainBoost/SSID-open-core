"""Basic chart.yaml validation for 23_compliance/05_gesundheit_medizin."""

import os

import pytest
import yaml

SHARD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_PATH = os.path.join(SHARD_DIR, "chart.yaml")


@pytest.fixture
def chart():
    """Load chart.yaml via safe_load."""
    with open(CHART_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_chart_loads(chart):
    """chart.yaml must be valid YAML."""
    assert chart is not None


def test_capabilities_not_empty(chart):
    """Capabilities must define at least one MUST item."""
    caps = chart.get("capabilities", {})
    must = caps.get("must", [])
    assert len(must) > 0, "capabilities.must must not be empty"


def test_policy_hash_only(chart):
    """Policy hash_only must be present."""
    policies = chart.get("policies", [])
    ids = [p.get("id") for p in policies]
    assert "hash_only" in ids, "hash_only policy required"


def test_policy_non_custodial(chart):
    """Policy non_custodial must be present."""
    policies = chart.get("policies", [])
    ids = [p.get("id") for p in policies]
    assert "non_custodial" in ids, "non_custodial policy required"


def test_version_present(chart):
    """Version field must exist."""
    assert "version" in chart, "version field required in chart.yaml"
