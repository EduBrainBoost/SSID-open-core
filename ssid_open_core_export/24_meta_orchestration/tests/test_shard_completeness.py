"""
Shard-Level Completeness Tests for Root 24_meta_orchestration.

Validates that all 16 canonical shards exist with required artifacts
(chart.yaml, manifest.yaml) and that chart.yaml is parsable with
non-empty capabilities.
"""

from pathlib import Path

import pytest
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
ROOT_NAME = ROOT_DIR.name  # "24_meta_orchestration"

SHARD_NAMES = [
    "01_identitaet_personen",
    "02_dokumente_nachweise",
    "03_zugang_berechtigungen",
    "04_kommunikation_daten",
    "05_gesundheit_medizin",
    "06_bildung_qualifikationen",
    "07_familie_soziales",
    "08_mobilitaet_fahrzeuge",
    "09_arbeit_karriere",
    "10_finanzen_banking",
    "11_versicherungen_risiken",
    "12_immobilien_grundstuecke",
    "13_unternehmen_gewerbe",
    "14_vertraege_vereinbarungen",
    "15_handel_transaktionen",
    "16_behoerden_verwaltung",
]


@pytest.fixture
def root_path():
    return ROOT_DIR


@pytest.fixture
def shards_path(root_path):
    return root_path / "shards"


# --- Existence tests ---


def test_all_16_shards_exist(shards_path):
    """All 16 canonical shard directories must be present."""
    missing = [s for s in SHARD_NAMES if not (shards_path / s).is_dir()]
    assert not missing, f"Missing shard directories in {ROOT_NAME}: {missing}"


@pytest.mark.parametrize("shard", SHARD_NAMES)
def test_chart_exists(shard, shards_path):
    """Every shard must contain a chart.yaml."""
    chart = shards_path / shard / "chart.yaml"
    assert chart.exists(), f"{ROOT_NAME}/{shard}: chart.yaml missing"


@pytest.mark.parametrize("shard", SHARD_NAMES)
def test_manifest_exists(shard, shards_path):
    """Every shard must contain a manifest.yaml."""
    manifest = shards_path / shard / "manifest.yaml"
    assert manifest.exists(), f"{ROOT_NAME}/{shard}: manifest.yaml missing"


# --- Parsability tests ---


@pytest.mark.parametrize("shard", SHARD_NAMES)
def test_chart_parsable(shard, shards_path):
    """chart.yaml must be valid YAML (parsable by yaml.safe_load)."""
    chart = shards_path / shard / "chart.yaml"
    if not chart.exists():
        pytest.skip(f"chart.yaml not found for {shard}")
    text = chart.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        pytest.fail(f"{ROOT_NAME}/{shard}: chart.yaml is not valid YAML: {exc}")
    assert isinstance(data, dict), (
        f"{ROOT_NAME}/{shard}: chart.yaml top-level must be a mapping, got {type(data).__name__}"
    )


# --- Content / capabilities tests ---


@pytest.mark.parametrize("shard", SHARD_NAMES)
def test_capabilities_not_empty(shard, shards_path):
    """chart.yaml must declare at least one capability for draft (or higher) status shards."""
    chart = shards_path / shard / "chart.yaml"
    if not chart.exists():
        pytest.skip(f"chart.yaml not found for {shard}")
    data = yaml.safe_load(chart.read_text(encoding="utf-8"))
    status = data.get("status", "unknown")
    # scaffold shards may have empty capabilities; draft and above must not
    if status == "scaffold":
        pytest.skip(f"{ROOT_NAME}/{shard} is scaffold — capabilities check deferred")
    caps = data.get("capabilities", {})
    if caps is None:
        caps = {}
    all_caps = []
    for priority in ("must", "should", "could", "would"):
        entries = caps.get(priority)
        if entries:
            all_caps.extend(entries)
    assert len(all_caps) > 0, (
        f"{ROOT_NAME}/{shard} (status={status}): capabilities must not be empty "
        f"(at least draft-status shards need capabilities)"
    )
