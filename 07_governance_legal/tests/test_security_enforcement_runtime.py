from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "07_governance_legal" / "src"))
sys.path.insert(0, str(ROOT / "12_tooling" / "cli"))

from chart_manifest_bootstrap import run_bootstrap
from wave07_security_enforcement import (
    Root07SecurityEnforcementWave,
    SecurityPolicyDeniedError,
    SecurityRuntimeDependencyError,
)


def test_root07_security_allows_hash_only_payload_for_priority_shard(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root07SecurityEnforcementWave(tmp_path)

    result, evidence = wave.run(
        "01_identitaet_personen",
        {"request_id": "sec-0001", "payload_hash": "a" * 64},
    )

    assert result["status"] == "accepted"
    assert evidence.decision == "allow"
    assert evidence.shard_id == "01_identitaet_personen"
    assert evidence.dependency_refs == [
        "03_core/01_identitaet_personen",
        "09_meta_identity/01_identitaet_personen",
    ]
    assert evidence.audit_event.endswith("security_runtime_audit.jsonl")


def test_root07_security_denies_pii_payload(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root07SecurityEnforcementWave(tmp_path)

    try:
        wave.run(
            "01_identitaet_personen",
            {
                "request_id": "sec-0002",
                "payload_hash": "b" * 64,
                "email_address": "user@example.com",
            },
        )
    except SecurityPolicyDeniedError as exc:
        assert "pii" in str(exc).lower()
    else:
        raise AssertionError("expected SecurityPolicyDeniedError")


def test_root07_security_fails_closed_on_missing_runtime_dependency(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    dependency = tmp_path / "09_meta_identity" / "shards" / "01_identitaet_personen" / "runtime" / "index.yaml"
    dependency.unlink()
    wave = Root07SecurityEnforcementWave(tmp_path)

    try:
        wave.run("01_identitaet_personen", {"request_id": "sec-0003", "payload_hash": "c" * 64})
    except SecurityRuntimeDependencyError as exc:
        assert "missing runtime dependency" in str(exc)
    else:
        raise AssertionError("expected SecurityRuntimeDependencyError")


def test_root07_security_is_deterministic_for_same_input(tmp_path: Path) -> None:
    run_bootstrap(tmp_path)
    wave = Root07SecurityEnforcementWave(tmp_path)
    payload = {"request_id": "sec-0004", "payload_hash": "d" * 64}

    result_a, evidence_a = wave.run("03_verifiable_credentials", payload)
    result_b, evidence_b = wave.run("03_verifiable_credentials", payload)

    assert result_a == result_b
    assert evidence_a.input_sha256 == evidence_b.input_sha256
    assert evidence_a.output_sha256 == evidence_b.output_sha256
