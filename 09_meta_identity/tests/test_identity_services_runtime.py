from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "03_core" / "src"))
sys.path.insert(0, str(ROOT / "09_meta_identity" / "src"))
sys.path.insert(0, str(ROOT / "12_tooling" / "cli"))

from chart_manifest_bootstrap import run_bootstrap
from reference_services import ServiceContractError
from wave09_identity_services import Root09IdentityServicesWave, ServiceDependencyError


def test_root09_identity_services_runs_priority_service_with_core_binding(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root09IdentityServicesWave(tmp_path)

    result, evidence = wave.run(
        "01_identitaet_personen",
        {"request_id": "svc-0001", "payload_hash": "a" * 64},
    )

    assert result["status"] == "accepted"
    assert result["result_id"] == "svc-0001"
    assert evidence.shard_id == "01_identitaet_personen"
    assert evidence.dependency_refs == ["03_core/01_identitaet_personen"]
    assert evidence.audit_event.endswith("service_runtime_audit.jsonl")


def test_root09_identity_services_fails_closed_when_core_dependency_is_missing(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    dependency = tmp_path / "03_core" / "shards" / "01_identitaet_personen" / "runtime" / "index.yaml"
    dependency.unlink()

    wave = Root09IdentityServicesWave(tmp_path)
    try:
        wave.run("01_identitaet_personen", {"request_id": "svc-0002", "payload_hash": "b" * 64})
    except ServiceDependencyError as exc:
        assert "missing core runtime dependency" in str(exc)
    else:
        raise AssertionError("expected ServiceDependencyError")


def test_root09_identity_services_supports_cross_root_orchestration_alias(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root09IdentityServicesWave(tmp_path)

    result, evidence = wave.run(
        "03_verifiable_credentials",
        {"request_id": "svc-0003", "payload_hash": "c" * 64},
    )

    assert result["status"] == "accepted"
    assert evidence.dependency_refs == ["03_core/03_shard_03"]


def test_root09_identity_services_fails_closed_on_invalid_input(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root09IdentityServicesWave(tmp_path)

    try:
        wave.run("01_identitaet_personen", {"request_id": "short"})
    except ServiceContractError as exc:
        assert "payload_hash" in str(exc)
    else:
        raise AssertionError("expected ServiceContractError")


def test_root09_identity_services_is_deterministic_for_same_input(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root09IdentityServicesWave(tmp_path)
    payload = {"request_id": "svc-0004", "payload_hash": "d" * 64}

    result_a, evidence_a = wave.run("04_did_resolution", payload)
    result_b, evidence_b = wave.run("04_did_resolution", payload)

    assert result_a == result_b
    assert evidence_a.input_sha256 == evidence_b.input_sha256
    assert evidence_a.output_sha256 == evidence_b.output_sha256


def test_root09_identity_services_supports_end_to_end_orchestration_flow(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root09IdentityServicesWave(tmp_path)

    identity_result, identity_evidence = wave.run(
        "01_identitaet_personen",
        {"request_id": "svc-0005", "payload_hash": "e" * 64},
    )
    document_result, document_evidence = wave.run(
        "02_dokumente_nachweise",
        {"request_id": "svc-0006", "payload_hash": "f" * 64},
    )
    vc_result, vc_evidence = wave.run(
        "03_verifiable_credentials",
        {"request_id": "svc-0007", "payload_hash": "a" * 64},
    )

    assert identity_result["status"] == "accepted"
    assert document_result["status"] == "accepted"
    assert vc_result["status"] == "accepted"
    assert identity_evidence.dependency_refs == ["03_core/01_identitaet_personen"]
    assert document_evidence.dependency_refs == ["03_core/02_dokumente_nachweise"]
    assert vc_evidence.dependency_refs == ["03_core/03_shard_03"]
