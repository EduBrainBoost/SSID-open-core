from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SecurityEnforcementError(Exception):
    pass


class SecurityPolicyDeniedError(SecurityEnforcementError):
    pass


class SecurityRuntimeDependencyError(SecurityEnforcementError):
    pass


@dataclass(frozen=True)
class SecurityEvidence:
    root_id: str
    shard_id: str
    operation: str
    decision: str
    blocking_reason: str | None
    input_sha256: str
    output_sha256: str
    dependency_refs: list[str]
    audit_event: str


def _sha256_payload(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


class SecurityPolicyEngine:
    PII_KEYS = {"email", "email_address", "phone", "phone_number", "full_name", "ssn", "token", "secret"}
    RAW_DENY_KEYS = {"raw_payload", "persisted_payload", "plain_text", "secret_value"}

    def evaluate(self, payload: dict[str, Any]) -> tuple[str, str | None]:
        keys = {str(key).lower() for key in payload}
        if keys & self.PII_KEYS:
            return "deny", "pii_detected"
        if keys & self.RAW_DENY_KEYS:
            return "deny", "direct_data_persistence_detected"
        if "payload_hash" not in payload:
            return "deny", "proof_hash_missing"
        return "allow", None


class SecurityEnforcementBridge:
    def __init__(self, shard_dir: Path, dependency_refs: list[str]):
        self.shard_dir = shard_dir
        self.evidence_dir = shard_dir / "evidence"
        self.dependency_refs = dependency_refs
        self.policy_engine = SecurityPolicyEngine()

    def enforce(self, payload: dict[str, Any]) -> tuple[dict[str, Any], SecurityEvidence]:
        decision, blocking_reason = self.policy_engine.evaluate(payload)
        if decision != "allow":
            result = {
                "result_id": payload.get("request_id", "unknown"),
                "status": "rejected",
            }
            evidence = self._write_evidence(payload, result, decision, blocking_reason)
            raise SecurityPolicyDeniedError(blocking_reason or "security policy denied")
        result = {
            "result_id": payload["request_id"],
            "status": "accepted",
        }
        evidence = self._write_evidence(payload, result, "allow", None)
        return result, evidence

    def _write_evidence(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        decision: str,
        blocking_reason: str | None,
    ) -> SecurityEvidence:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "security_event_id": f"{self.shard_dir.name}:{payload.get('request_id', 'unknown')}",
            "root_id": "07_governance_legal",
            "shard_id": self.shard_dir.name,
            "operation": "security_enforce",
            "decision": decision,
            "blocking_reason": blocking_reason,
            "dependency_refs": self.dependency_refs,
            "input_sha256": _sha256_payload(payload),
            "output_sha256": _sha256_payload(result),
        }
        event_path = self.evidence_dir / "security_runtime_audit.jsonl"
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return SecurityEvidence(
            root_id="07_governance_legal",
            shard_id=self.shard_dir.name,
            operation="security_enforce",
            decision=decision,
            blocking_reason=blocking_reason,
            input_sha256=event["input_sha256"],
            output_sha256=event["output_sha256"],
            dependency_refs=self.dependency_refs,
            audit_event=event_path.as_posix(),
        )
