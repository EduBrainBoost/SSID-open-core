"""Basic conformance tests for 16_codex/12_immobilien_grundstuecke."""
import os
import yaml


SHARD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_PATH = os.path.join(SHARD_DIR, "chart.yaml")


def _load_chart():
    with open(CHART_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_chart_loads():
    chart = _load_chart()
    assert isinstance(chart, dict), "chart.yaml must parse to a dict"


def test_capabilities_not_empty():
    chart = _load_chart()
    caps = chart.get("capabilities", {})
    must = caps.get("must", [])
    assert len(must) > 0, "capabilities.must must not be empty"


def test_policies_hash_only_and_non_custodial():
    chart = _load_chart()
    policies = chart.get("policies", [])
    ids = [p.get("id") for p in policies if isinstance(p, dict)]
    assert "hash_only" in ids, "hash_only policy required"
    assert "non_custodial" in ids, "non_custodial policy required"


def test_version_present():
    chart = _load_chart()
    assert "version" in chart, "version field required in chart.yaml"
    assert chart["version"], "version must not be empty"
