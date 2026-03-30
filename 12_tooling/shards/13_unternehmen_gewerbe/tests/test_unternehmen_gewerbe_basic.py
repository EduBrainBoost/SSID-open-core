"""Basic tests for 12_tooling / 13_unternehmen_gewerbe."""
import os
import yaml
import pytest


SHARD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_PATH = os.path.join(SHARD_DIR, "chart.yaml")


@pytest.fixture
def chart():
    with open(CHART_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_chart_loads(chart):
    assert chart is not None, "chart.yaml must load successfully"


def test_capabilities_not_empty(chart):
    caps = chart.get("capabilities", {})
    must = caps.get("must", [])
    assert len(must) > 0, "capabilities.must must not be empty"


def test_policy_hash_only(chart):
    policies = chart.get("policies", [])
    ids = [p.get("id") for p in policies]
    assert "hash_only" in ids, "hash_only policy required"


def test_policy_non_custodial(chart):
    policies = chart.get("policies", [])
    ids = [p.get("id") for p in policies]
    assert "non_custodial" in ids, "non_custodial policy required"


def test_version_present(chart):
    assert chart.get("version"), "version must be present"


def test_shard_name_correct(chart):
    assert chart.get("shard") == "13_unternehmen_gewerbe", f"shard must be 13_unternehmen_gewerbe"
