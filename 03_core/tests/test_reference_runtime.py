from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "03_core" / "src"))
sys.path.insert(0, str(ROOT / "12_tooling" / "cli"))

from chart_manifest_bootstrap import run_bootstrap
from wave03_reference import Root03ReferenceWave


def test_root03_reference_wave_processes_priority_shard(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root03ReferenceWave(tmp_path)

    result, evidence = wave.run(
        "01_identitaet_personen",
        {"request_id": "req-0001", "payload_hash": "a" * 64},
    )

    assert result["status"] == "accepted"
    assert evidence.shard_id == "01_identitaet_personen"
    assert len(evidence.input_sha256) == 64
    assert len(evidence.output_sha256) == 64
    assert evidence.audit_event.endswith("runtime_audit.jsonl")


def test_root03_reference_wave_exposes_priority_shards(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root03ReferenceWave(tmp_path)
    assert wave.available_shards()[:5] == [
        "01_identitaet_personen",
        "02_dokumente_nachweise",
        "03_shard_03",
        "04_shard_04",
        "05_shard_05",
    ]


def test_root03_reference_wave_supports_alias_shards(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root03ReferenceWave(tmp_path)
    result, evidence = wave.run(
        "03_verifiable_credentials",
        {"request_id": "req-0002", "payload_hash": "b" * 64},
    )
    assert result["status"] == "accepted"
    assert evidence.shard_id == "03_shard_03"


def test_root03_reference_wave_runs_document_and_did_paths(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root03ReferenceWave(tmp_path)

    document_result, _ = wave.run(
        "02_dokumente_nachweise",
        {"request_id": "req-0003", "payload_hash": "c" * 64},
    )
    did_result, _ = wave.run(
        "04_did_resolution",
        {"request_id": "req-0004", "payload_hash": "d" * 64},
    )

    assert document_result["status"] == "accepted"
    assert did_result["status"] == "accepted"


def test_root03_reference_service_serializes_result(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root03ReferenceWave(tmp_path)
    payload, evidence = wave.service_for("05_claims_binding").execute(
        {"request_id": "req-0005", "payload_hash": "e" * 64},
    )

    assert payload == '{"result_id":"req-0005","status":"accepted"}'
    assert evidence.shard_id == "05_shard_05"
