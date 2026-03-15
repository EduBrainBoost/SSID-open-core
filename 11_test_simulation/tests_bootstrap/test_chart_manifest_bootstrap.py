from __future__ import annotations

import json
import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[2] / "12_tooling" / "cli"
sys.path.insert(0, str(CLI_DIR))

from chart_manifest_bootstrap import run_bootstrap
from shard_conformance_gate import _check_shard


def test_bootstrap_generates_expected_counts(tmp_path: Path) -> None:
    report = run_bootstrap(tmp_path)

    chart_files = list(tmp_path.rglob("chart.yaml"))
    manifest_files = list(tmp_path.rglob("manifest.yaml"))
    taskspecs = list((tmp_path / "24_meta_orchestration" / "registry").glob("TASKSPEC_*.yaml"))

    assert report["chart_count"] == 384
    assert report["manifest_count"] == 384
    assert len(chart_files) == 384
    assert len(manifest_files) == 384
    assert len(taskspecs) == 24


def test_bootstrap_creates_pilot_conformance_assets(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)

    shard_dir = tmp_path / "03_core" / "shards" / "01_identitaet_personen"
    result = _check_shard("03_core", shard_dir)

    assert result["verdict"] == "PASS"
    assert result["checks"]["contracts_exist"] is True
    assert result["checks"]["schema_valid"] is True
    assert result["checks"]["valid_fixtures_pass"] is True
    assert result["checks"]["invalid_fixtures_rejected"] is True


def test_bootstrap_writes_registry_and_agent_log(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)

    registry_path = tmp_path / "24_meta_orchestration" / "registry" / "shards_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    log_path = tmp_path / "02_audit_logging" / "agent_runs" / "AI_CLI_INTEGRATION_LOG.jsonl"

    assert registry["shard_count"] == 384
    assert log_path.exists()
    assert "chart_manifest_bootstrap" in log_path.read_text(encoding="utf-8")
