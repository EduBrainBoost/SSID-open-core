"""ems_contract.py — EMS-compatible payload and evidence schema definitions.

P4.5: Stable contract for SSID → EMS integration after PR#127 merge.

All types are JSON-serializable (str, int, float, list, dict, None).
No external dependencies.

Used by EMS after merge of PR#127 to consume:
- Flow execution status
- Policy enforcement decisions
- Evidence artefacts
- Runtime health of modules
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Schema version — increment when fields change
SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Status Taxonomy — canonical status values for SSID↔EMS contract
# ---------------------------------------------------------------------------


# Flow execution status
class FlowStatus:
    HEALTHY = "success"  # flow completed successfully, all policies ALLOW
    DENIED = "denied"  # flow blocked by PolicyEnforcer (DENY decision)
    DEGRADED = "degraded"  # flow partially completed or non-critical error
    FAILED = "error"  # flow raised an unhandled exception


# Evidence presence status
class EvidenceStatus:
    PRESENT = "present"  # FlowEvidence generated with valid proof_hash
    MISSING = "missing"  # flow ran but no evidence was persisted
    INVALID = "invalid"  # evidence exists but proof_hash does not verify


# Contract validation status
class ContractStatus:
    VALID = "valid"  # report passes schema + version checks
    SCHEMA_MISMATCH = "schema_mismatch"  # JSON Schema validation failed
    VERSION_MISMATCH = "version_mismatch"  # MAJOR version incompatible
    INCOMPLETE = "incomplete"  # required fields missing from report


# Module health status
class ModuleHealthStatus:
    HEALTHY = "healthy"  # module is importable and functional
    DEGRADED = "degraded"  # module has partial functionality or non-critical errors
    OFFLINE = "offline"  # module is not importable or unresponsive


# Overall system status (top-level report classification)
class OverallStatus:
    HEALTHY = "healthy"  # all modules healthy, all flows succeeded
    DENIED = "denied"  # at least one flow was denied by policy
    DEGRADED = "degraded"  # at least one module/flow is degraded/offline/error
    ERROR = "error"  # reporter itself failed or contract is invalid


# Error codes for EMS consumers
class ErrorCode:
    OK = 0  # healthy
    DENIED = 1  # policy denial
    DEGRADED = 2  # partial degradation
    INVALID_SCHEMA = 3  # schema validation failed
    VERSION_MISMATCH = 4  # incompatible MAJOR version
    INCOMPLETE = 5  # required fields missing


# Operator response per status
OPERATOR_ACTIONS: dict[str, str] = {
    OverallStatus.HEALTHY: "No action required. System is operating normally.",
    OverallStatus.DENIED: "REQUIRED: Review PolicyDecisionPayload.reason. Escalate to compliance team or fix upstream inputs.",
    OverallStatus.DEGRADED: "RECOMMENDED: Check ModuleHealthPayload.detail for affected modules. Restore dependencies and re-probe.",
    OverallStatus.ERROR: "REQUIRED: Check reporter logs. Re-run SsidRuntimeReporter after fixing root cause.",
    ContractStatus.SCHEMA_MISMATCH: "REQUIRED: Update EMS consumer to match new schema. Review CHANGELOG for breaking changes.",
    ContractStatus.VERSION_MISMATCH: "REQUIRED: Align SSID and EMS versions. Check CONTRACT_GOVERNANCE.md for migration steps.",
    ContractStatus.INCOMPLETE: "REQUIRED: Report is missing required fields. Check SsidRuntimeReporter version.",
}


@dataclass
class PolicyDecisionPayload:
    """Serializable policy decision for EMS consumption."""

    action: str  # "allow" | "deny"
    rule_type: str | None  # e.g. "max_fee", "min_participants"
    reason: str
    context: dict[str, str]  # all values stringified
    decided_at: str  # ISO-8601

    @classmethod
    def from_evidence_dict(cls, d: dict[str, Any]) -> PolicyDecisionPayload:
        return cls(
            action=d["action"],
            rule_type=d.get("rule_type"),
            reason=d["reason"],
            context={k: str(v) for k, v in d.get("context", {}).items()},
            decided_at=d["decided_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "rule_type": self.rule_type,
            "reason": self.reason,
            "context": self.context,
            "decided_at": self.decided_at,
        }


@dataclass
class FlowStatusPayload:
    """Runtime status of a SSID core flow execution — consumed by EMS."""

    flow_id: str
    flow_name: str
    status: str  # "success" | "denied" | "error"
    allow_or_deny: str
    input_hash: str
    output_hash: str
    proof_hash: str | None
    determinism_hash: str
    policy_decisions: list[dict[str, Any]]
    timestamp_utc: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
            "status": self.status,
            "allow_or_deny": self.allow_or_deny,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "proof_hash": self.proof_hash,
            "determinism_hash": self.determinism_hash,
            "policy_decisions": self.policy_decisions,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass
class ModuleHealthPayload:
    """Health status of a SSID module — consumed by EMS for runtime visibility."""

    module_name: str
    status: str  # "healthy" | "degraded" | "offline"
    version: str
    last_checked_utc: str

    def to_dict(self) -> dict[str, str]:
        return {
            "module_name": self.module_name,
            "status": self.status,
            "version": self.version,
            "last_checked_utc": self.last_checked_utc,
        }


CORE_MODULES = [
    "fee_distribution_engine",
    "subscription_revenue_distributor",
    "governance_reward_engine",
    "license_fee_splitter",
    "identity_fee_router",
    "reward_handler",
    "fee_proof_engine",
    "policy_enforcer",
]


def get_module_health_payloads(version: str = "1.0.0") -> list[ModuleHealthPayload]:
    """Return health payload for all core modules (all healthy by default)."""
    now = datetime.now(UTC).isoformat()
    return [
        ModuleHealthPayload(module_name=m, status="healthy", version=version, last_checked_utc=now)
        for m in CORE_MODULES
    ]
