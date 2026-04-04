import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ems.services.sot_promotion_service import load_active_baseline_state

FREEZE_LEVELS = {"none", "watch", "soft_freeze", "hard_freeze", "emergency_stop"}
OPERATION_TYPES = {"promotion_execute", "rollback_evaluate", "rollback_execute"}
ALLOWED_SCOPES = {"canonical_sot", "global", "recovery"}


class FreezeGovernanceError(RuntimeError):
    def __init__(
        self,
        finding_code: str,
        detail: str,
        *,
        http_status: int = 409,
        findings: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.finding_code = finding_code
        self.http_status = http_status
        base_findings = list(findings or [])
        if not base_findings:
            base_findings.append(_finding(finding_code, "deny", "freeze", detail))
        if finding_code != "freeze_governance_fail_closed":
            base_findings.append(
                _finding(
                    "freeze_governance_fail_closed",
                    "deny",
                    "freeze",
                    "incident freeze governance failed closed",
                )
            )
        self.findings = base_findings


def _finding(finding_code: str, severity: str, path: str, detail: str) -> dict[str, str]:
    return {
        "finding_code": finding_code,
        "severity": severity,
        "path": path,
        "detail": detail,
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _freeze_state_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_incident_freeze_state.json"


def _freeze_decisions_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_incident_freeze_decisions.jsonl"


def _release_block_report_path(repo_root: Path) -> Path:
    return repo_root / "02_audit_logging" / "reports" / "sot_release_block_report.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"freeze_state_missing: required registry file missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            f"freeze state is not valid JSON: {exc}",
            http_status=500,
        ) from exc


def load_freeze_state(repo_root: Path) -> dict[str, Any]:
    payload = _read_json(_freeze_state_path(repo_root))
    required_fields = {
        "state_id",
        "updated_at_utc",
        "freeze_level",
        "incident_id",
        "reason",
        "set_by",
        "scope",
        "evidence_hash",
    }
    missing = sorted(field for field in required_fields if field not in payload)
    if missing:
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            f"freeze state missing required fields: {', '.join(missing)}",
            http_status=500,
        )
    if payload["freeze_level"] not in FREEZE_LEVELS:
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            f"invalid freeze level '{payload['freeze_level']}'",
            http_status=500,
        )
    if not isinstance(payload["reason"], str) or not payload["reason"].strip():
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            "freeze state reason must be non-empty",
            http_status=500,
        )
    computed = _json_sha256({k: v for k, v in payload.items() if k != "evidence_hash"})
    if payload["evidence_hash"] != computed:
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            "freeze state evidence hash mismatch",
            http_status=500,
        )
    return payload


def write_freeze_state(
    repo_root: Path,
    freeze_level: str,
    reason: str,
    set_by: str,
    incident_id: str,
    scope: str,
) -> dict[str, Any]:
    if freeze_level not in FREEZE_LEVELS:
        raise FreezeGovernanceError("freeze_state_invalid", f"invalid freeze level '{freeze_level}'")
    if not reason.strip() or not set_by.strip() or not incident_id.strip() or not scope.strip():
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            "freeze state requires freeze_level, reason, set_by, incident_id and scope",
        )
    payload = {
        "state_id": f"FRZ-{uuid.uuid4().hex[:12].upper()}",
        "updated_at_utc": _utc_now_iso(),
        "freeze_level": freeze_level,
        "incident_id": incident_id,
        "reason": reason.strip(),
        "set_by": set_by.strip(),
        "scope": scope.strip(),
    }
    payload["evidence_hash"] = _json_sha256(payload)
    path = _freeze_state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def emit_freeze_governance_decision(
    repo_root: Path,
    *,
    operation_type: str,
    freeze_level: str,
    decision: str,
    allowed: bool,
    reason: str,
    candidate_id: str | None = None,
    proposal_id: str | None = None,
) -> dict[str, Any]:
    if operation_type not in OPERATION_TYPES:
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            f"invalid freeze governance operation '{operation_type}'",
            http_status=500,
        )
    payload = {
        "decision_id": f"FGD-{uuid.uuid4().hex[:12].upper()}",
        "decided_at_utc": _utc_now_iso(),
        "operation_type": operation_type,
        "candidate_id": candidate_id,
        "proposal_id": proposal_id,
        "freeze_level": freeze_level,
        "decision": decision,
        "allowed": allowed,
        "reason": reason,
    }
    payload["decision_evidence_hash"] = _json_sha256(payload)
    path = _freeze_decisions_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
    except Exception as exc:
        raise FreezeGovernanceError(
            "freeze_governance_log_write_failed",
            f"failed to write freeze governance decision: {exc}",
            http_status=500,
        ) from exc
    return payload


def evaluate_promotion_freeze_gate(
    repo_root: Path,
    *,
    candidate_id: str,
    reason: str,
) -> dict[str, Any]:
    state = load_freeze_state(repo_root)
    level = state["freeze_level"]
    if level == "none":
        decision, allowed = "PASS", True
    elif level == "watch":
        decision, allowed = "WARN", True
    else:
        decision, allowed = "FAIL", False
    decision_record = emit_freeze_governance_decision(
        repo_root,
        operation_type="promotion_execute",
        candidate_id=candidate_id,
        freeze_level=level,
        decision=decision,
        allowed=allowed,
        reason=reason,
    )
    result = {"freeze_state": state, "decision_record": decision_record, "allowed": allowed, "decision": decision}
    if not allowed:
        raise FreezeGovernanceError(
            "promotion_blocked_by_freeze",
            f"promotion execute is blocked by freeze level '{level}'",
        )
    return result


def evaluate_emergency_recovery_override(
    repo_root: Path,
    *,
    proposal_id: str | None,
    reason: str,
    target_baseline_version: str,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not reason.strip():
        findings.append(
            _finding(
                "emergency_recovery_override_denied",
                "deny",
                "override.reason",
                "emergency recovery override requires a reason",
            )
        )
    active_state = load_active_baseline_state(repo_root)
    if active_state.get("consistency_status") != "CONSISTENT":
        findings.append(
            _finding(
                "rollback_active_state_invalid",
                "deny",
                "active_state.consistency_status",
                "active state is inconsistent for emergency recovery override",
            )
        )
    try:
        release_block_report = _read_json(_release_block_report_path(repo_root))
    except FileNotFoundError:
        findings.append(
            _finding(
                "rollback_release_state_invalid",
                "deny",
                str(_release_block_report_path(repo_root)),
                "release blocker report is missing for emergency recovery override",
            )
        )
        release_block_report = {"decision": "FAIL"}
    if release_block_report.get("decision") not in {"PASS", "WARN"}:
        findings.append(
            _finding(
                "rollback_release_state_invalid",
                "deny",
                "release_block_report.decision",
                "release blocker state is invalid for emergency recovery override",
            )
        )
    if active_state.get("scope") not in ALLOWED_SCOPES:
        findings.append(
            _finding(
                "emergency_recovery_override_denied",
                "deny",
                "active_state.scope",
                "active state scope is not eligible for emergency recovery override",
            )
        )
    if not target_baseline_version.strip():
        findings.append(
            _finding(
                "emergency_recovery_override_denied",
                "deny",
                "proposal.target_baseline_version",
                "recovery target version is required for emergency override evaluation",
            )
        )
    return {
        "allowed": not findings,
        "decision": "PASS" if not findings else "FAIL",
        "findings": findings,
        "proposal_id": proposal_id,
    }


def evaluate_recovery_freeze_gate(
    repo_root: Path,
    *,
    operation_type: str,
    reason: str,
    proposal_id: str | None = None,
    target_baseline_version: str | None = None,
) -> dict[str, Any]:
    if operation_type not in {"rollback_evaluate", "rollback_execute"}:
        raise FreezeGovernanceError(
            "freeze_state_invalid",
            f"invalid recovery freeze operation '{operation_type}'",
            http_status=500,
        )
    state = load_freeze_state(repo_root)
    level = state["freeze_level"]
    allowed = True
    decision = "PASS"
    override_result: dict[str, Any] | None = None

    if operation_type == "rollback_evaluate":
        if level == "watch" or level == "emergency_stop":
            decision = "WARN"
    else:
        if level == "watch":
            decision = "WARN"
        elif level == "hard_freeze" or level == "emergency_stop":
            override_result = evaluate_emergency_recovery_override(
                repo_root,
                proposal_id=proposal_id,
                reason=reason,
                target_baseline_version=target_baseline_version or "",
            )
            allowed = override_result["allowed"]
            decision = "PASS" if allowed else "FAIL"

    decision_record = emit_freeze_governance_decision(
        repo_root,
        operation_type=operation_type,
        proposal_id=proposal_id,
        freeze_level=level,
        decision=decision,
        allowed=allowed,
        reason=reason,
    )
    result = {
        "freeze_state": state,
        "decision_record": decision_record,
        "allowed": allowed,
        "decision": decision,
        "override": override_result,
    }
    if not allowed:
        code = (
            "rollback_evaluate_blocked_by_freeze"
            if operation_type == "rollback_evaluate"
            else "recovery_blocked_by_freeze"
        )
        findings = list((override_result or {}).get("findings", []))
        raise FreezeGovernanceError(
            code,
            f"{operation_type} is blocked by freeze level '{level}'",
            findings=findings or None,
        )
    return result
