"""FlowEvidence — standardized evidence artefact for every SSID core flow.

Schema (P4.2 Evidence Contract):
  flow_id          str     unique run identifier
  flow_name        str     e.g. "subscription_revenue", "license_fee", "reward_governance"
  input_hash       str     SHA-256 of serialized inputs
  output_hash      str     SHA-256 of serialized outputs
  policy_decisions list    from PolicyEnforcer.export_evidence()
  allow_or_deny    str     "allow" or "deny"
  proof_hash       str | None  from FeeProofEngine if applicable
  timestamp_utc    str     ISO-8601
  module_versions  dict    module_name -> version string
  determinism_hash str     SHA-256 of (input_hash + output_hash)

EMS-compatible: every field is a str, list[dict], or dict[str, str].
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_VERSION = "1.0.0"

MODULE_VERSIONS: dict[str, str] = {
    "fee_distribution_engine": _VERSION,
    "subscription_revenue_distributor": _VERSION,
    "governance_reward_engine": _VERSION,
    "license_fee_splitter": _VERSION,
    "identity_fee_router": _VERSION,
    "reward_handler": _VERSION,
    "fee_proof_engine": _VERSION,
    "policy_enforcer": _VERSION,
}


def _sha256(data: Any) -> str:
    payload = json.dumps(data, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class FlowEvidence:
    flow_id: str
    flow_name: str
    input_hash: str
    output_hash: str
    policy_decisions: list[dict[str, Any]]
    allow_or_deny: str
    proof_hash: str | None
    timestamp_utc: str
    module_versions: dict[str, str]
    determinism_hash: str

    @classmethod
    def create(
        cls,
        flow_name: str,
        inputs: Any,
        outputs: Any,
        policy_decisions: list[dict[str, Any]],
        allow_or_deny: str,
        proof_hash: str | None = None,
        flow_id: str | None = None,
    ) -> FlowEvidence:
        input_hash = _sha256(inputs)
        output_hash = _sha256(outputs)
        determinism_hash = _sha256(input_hash + output_hash)
        return cls(
            flow_id=flow_id or str(uuid.uuid4()),
            flow_name=flow_name,
            input_hash=input_hash,
            output_hash=output_hash,
            policy_decisions=policy_decisions,
            allow_or_deny=allow_or_deny,
            proof_hash=proof_hash,
            timestamp_utc=datetime.now(UTC).isoformat(),
            module_versions=MODULE_VERSIONS,
            determinism_hash=determinism_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "policy_decisions": self.policy_decisions,
            "allow_or_deny": self.allow_or_deny,
            "proof_hash": self.proof_hash,
            "timestamp_utc": self.timestamp_utc,
            "module_versions": self.module_versions,
            "determinism_hash": self.determinism_hash,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
