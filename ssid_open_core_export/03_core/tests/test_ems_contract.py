"""Tests for ems_contract.py — EMS-compatible schema P4.5."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ems_contract import (
    CORE_MODULES,
    SCHEMA_VERSION,
    FlowStatusPayload,
    ModuleHealthPayload,
    PolicyDecisionPayload,
    get_module_health_payloads,
)


def test_schema_version_is_string():
    assert isinstance(SCHEMA_VERSION, str)
    assert len(SCHEMA_VERSION) > 0


def test_core_modules_has_8_entries():
    assert len(CORE_MODULES) == 8


def test_policy_decision_payload_to_dict_keys():
    payload = PolicyDecisionPayload(
        action="allow",
        rule_type="max_fee",
        reason="Within limit",
        context={"fee": "100"},
        decided_at="2026-01-01T00:00:00+00:00",
    )
    d = payload.to_dict()
    assert set(d.keys()) == {"action", "rule_type", "reason", "context", "decided_at"}


def test_policy_decision_from_evidence_dict():
    evidence = {
        "action": "deny",
        "rule_type": "min_participants",
        "reason": "Not enough participants",
        "context": {"participants": 2, "required": 5},
        "decided_at": "2026-01-01T12:00:00+00:00",
    }
    payload = PolicyDecisionPayload.from_evidence_dict(evidence)
    assert payload.action == "deny"
    assert payload.rule_type == "min_participants"
    assert payload.reason == "Not enough participants"
    assert payload.context == {"participants": "2", "required": "5"}
    assert payload.decided_at == "2026-01-01T12:00:00+00:00"


def test_flow_status_payload_to_dict_json_serializable():
    payload = FlowStatusPayload(
        flow_id="flow-001",
        flow_name="fee_distribution",
        status="success",
        allow_or_deny="allow",
        input_hash="abc123",
        output_hash="def456",
        proof_hash=None,
        determinism_hash="ghi789",
        policy_decisions=[],
        timestamp_utc="2026-01-01T00:00:00+00:00",
    )
    d = payload.to_dict()
    # Must not raise
    serialized = json.dumps(d)
    assert isinstance(serialized, str)


def test_module_health_payload_to_dict():
    payload = ModuleHealthPayload(
        module_name="fee_distribution_engine",
        status="healthy",
        version="1.0.0",
        last_checked_utc="2026-01-01T00:00:00+00:00",
    )
    d = payload.to_dict()
    assert set(d.keys()) == {"module_name", "status", "version", "last_checked_utc"}


def test_get_module_health_payloads_returns_8():
    payloads = get_module_health_payloads()
    assert len(payloads) == 8
    assert all(p.status == "healthy" for p in payloads)


def test_flow_status_schema_version_matches():
    payload = FlowStatusPayload(
        flow_id="flow-002",
        flow_name="governance_reward",
        status="success",
        allow_or_deny="allow",
        input_hash="aaa",
        output_hash="bbb",
        proof_hash="ccc",
        determinism_hash="ddd",
        policy_decisions=[],
        timestamp_utc="2026-01-01T00:00:00+00:00",
    )
    assert payload.schema_version == SCHEMA_VERSION
