import hashlib
import importlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ems.services.sot_incident_freeze_governance import (
    FreezeGovernanceError,
    evaluate_promotion_freeze_gate,
)
from ems.services.sot_promotion_rollback_guard import evaluate_rollback_guard
from ems.services.sot_promotion_service import (
    RegistryConsistencyError,
    _candidate_registry_path,
    _read_json,
    _read_jsonl,
    get_candidate,
    list_operator_approvals,
)
from ems.services.sot_promotion_service import (
    load_active_baseline_state as load_current_active_state,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CLI_ROOT = _PROJECT_ROOT / "12_tooling" / "cli"
if str(_CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLI_ROOT))

_PROMOTION_GATE = importlib.import_module("sot_baseline_promotion_gate")
_REGISTRY_CONSUMER = importlib.import_module("sot_promotion_registry_consumer")
_RELEASE_BLOCKER = importlib.import_module("sot_release_blocker")
_OPERATOR_APPROVAL = importlib.import_module("sot_operator_approval")

REPORT_JSON_NAME = "sot_promotion_execution_result.json"
REPORT_MD_NAME = "sot_promotion_execution_result.md"


class ExecutionHandoffError(RuntimeError):
    def __init__(
        self,
        finding_code: str,
        detail: str,
        *,
        http_status: int = 500,
        findings: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.finding_code = finding_code
        self.http_status = http_status
        base_findings = list(findings or [])
        if not base_findings:
            base_findings.append(_finding(finding_code, "deny", "execution", detail))
        if finding_code != "execution_handoff_fail_closed":
            base_findings.append(
                _finding(
                    "execution_handoff_fail_closed",
                    "deny",
                    "execution",
                    "promotion execution handoff failed closed",
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


def _parse_version(version: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in version.split("."))
    except Exception:
        return None


def _reports_dir(repo_root: Path) -> Path:
    return repo_root / "02_audit_logging" / "reports"


def _promotions_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_baseline_promotions.jsonl"


def _snapshot_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_baseline_snapshot.json"


def _active_state_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_active_baseline_state.json"


def _execution_history_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_promotion_execution_history.jsonl"


def _release_block_report_path(repo_root: Path) -> Path:
    return repo_root / "02_audit_logging" / "reports" / "sot_release_block_report.json"


def _as_repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def load_candidate(repo_root: Path, candidate_id: str) -> dict[str, Any]:
    return get_candidate(repo_root, candidate_id)


def list_execution_history(repo_root: Path) -> list[dict[str, Any]]:
    try:
        items = _read_jsonl(_execution_history_path(repo_root))
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"execution_history_missing: required registry file missing: {_execution_history_path(repo_root)}"
        ) from exc
    items.sort(key=lambda item: item.get("executed_at_utc", ""))
    return items


def get_execution_history_item(repo_root: Path, execution_id: str) -> dict[str, Any]:
    for item in list_execution_history(repo_root):
        if item.get("execution_id") == execution_id:
            return item
    raise FileNotFoundError(f"execution_item_not_found: {execution_id}")


def write_execution_history_record(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = _execution_history_path(repo_root)
    record = dict(payload)
    record.setdefault("execution_id", f"EXEC-{uuid.uuid4().hex[:12].upper()}")
    record.setdefault("executed_at_utc", _utc_now_iso())
    record["execution_evidence_hash"] = _json_sha256(
        {k: v for k, v in record.items() if k != "execution_evidence_hash"}
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    except Exception as exc:
        raise ExecutionHandoffError(
            "execution_history_write_failed",
            f"failed to write execution history record: {exc}",
        ) from exc
    return record


def build_operator_audit_timeline(repo_root: Path) -> list[dict[str, Any]]:
    try:
        timeline: list[dict[str, Any]] = []
        candidate_records = _read_jsonl(_candidate_registry_path(repo_root))
        approval_records = list_operator_approvals(repo_root)
        execution_records = list_execution_history(repo_root)
        active_state = load_current_active_state(repo_root)
        release_report = _read_json(_release_block_report_path(repo_root))

        for record in candidate_records:
            timeline.append(
                {
                    "timestamp_utc": record.get("created_at_utc"),
                    "event_type": f"candidate_{record.get('status')}",
                    "candidate_id": record.get("candidate_id"),
                    "status": record.get("status"),
                    "detail": record.get("reason"),
                }
            )

        for record in approval_records:
            timeline.append(
                {
                    "timestamp_utc": record.get("decided_at_utc"),
                    "event_type": "operator_decision",
                    "candidate_id": record.get("candidate_id"),
                    "decision_id": record.get("decision_id"),
                    "status": record.get("decision"),
                    "approval_file": record.get("approval_file"),
                    "detail": record.get("reason"),
                }
            )

        for record in execution_records:
            timeline.append(
                {
                    "timestamp_utc": record.get("executed_at_utc"),
                    "event_type": "promotion_execution",
                    "candidate_id": record.get("candidate_id"),
                    "execution_id": record.get("execution_id"),
                    "promotion_id": record.get("promotion_id"),
                    "status": record.get("execution_status"),
                    "detail": record.get("reason"),
                }
            )

        timeline.append(
            {
                "timestamp_utc": active_state.get("updated_at_utc"),
                "event_type": "active_state_refreshed",
                "status": active_state.get("consistency_status"),
                "promotion_id": active_state.get("source_promotion_id"),
                "approval_id": active_state.get("source_approval_id"),
                "active_baseline_version": active_state.get("active_baseline_version"),
                "detail": "active baseline state refreshed",
            }
        )
        timeline.append(
            {
                "timestamp_utc": release_report.get("timestamp_utc"),
                "event_type": "release_block_result",
                "status": release_report.get("decision"),
                "detail": "latest release blocker result",
            }
        )
        timeline.append(
            {
                "timestamp_utc": active_state.get("updated_at_utc"),
                "event_type": "current_active_baseline",
                "status": active_state.get("decision"),
                "active_baseline_version": active_state.get("active_baseline_version"),
                "detail": "current active baseline",
            }
        )
        timeline.sort(key=lambda item: item.get("timestamp_utc", ""))
        return timeline
    except Exception as exc:
        raise RegistryConsistencyError(f"timeline_build_failed: {exc}") from exc


def validate_rollback_guard(
    repo_root: Path,
    requested_by: str,
    target_baseline_version: str,
    reason: str,
) -> dict[str, Any]:
    return evaluate_rollback_guard(
        repo_root=repo_root,
        requested_by=requested_by,
        target_baseline_version=target_baseline_version,
        reason=reason,
    )


def resolve_candidate_approval(repo_root: Path, candidate_id: str) -> dict[str, Any]:
    approvals = list_operator_approvals(repo_root)
    matching = [
        item for item in approvals if item.get("candidate_id") == candidate_id and item.get("decision") == "approve"
    ]
    if not matching:
        raise ExecutionHandoffError(
            "candidate_approval_missing",
            f"no approval decision found for candidate {candidate_id}",
            http_status=404,
        )
    decision = matching[-1]
    approval_file = decision.get("approval_file")
    if not approval_file:
        raise ExecutionHandoffError(
            "candidate_approval_missing",
            f"approval file is missing for candidate {candidate_id}",
            http_status=404,
        )
    approval_path = Path(str(approval_file))
    if not approval_path.is_absolute():
        approval_path = repo_root / approval_path
    if not approval_path.exists():
        raise ExecutionHandoffError(
            "candidate_approval_missing",
            f"approval artifact does not exist for candidate {candidate_id}: {approval_path}",
            http_status=404,
        )
    approval = _PROMOTION_GATE.load_promotion_approval(approval_path)
    if approval is None:
        raise ExecutionHandoffError(
            "candidate_approval_missing",
            f"approval artifact is unreadable for candidate {candidate_id}: {approval_path}",
            http_status=404,
        )
    approval = dict(approval)
    if "source_convergence_report" in approval:
        approval["source_convergence_report"] = str(
            _as_repo_path(repo_root, str(approval["source_convergence_report"]))
        )
    return {
        "decision_log_entry": decision,
        "approval_path": approval_path,
        "approval": approval,
    }


def validate_execution_preconditions(repo_root: Path, candidate_id: str) -> dict[str, Any]:
    candidate = load_candidate(repo_root, candidate_id)
    if candidate.get("status") != "approved":
        raise ExecutionHandoffError(
            "candidate_not_approved",
            f"candidate {candidate_id} has status '{candidate.get('status')}', expected approved",
            http_status=409,
        )

    approval_context = resolve_candidate_approval(repo_root, candidate_id)
    approval = approval_context["approval"]
    approval_path = approval_context["approval_path"]

    schema_findings = _PROMOTION_GATE.validate_approval_schema(approval)
    if schema_findings:
        raise ExecutionHandoffError(
            "candidate_execution_precondition_failed",
            "approval schema is invalid for execution handoff",
            findings=schema_findings,
        )

    convergence_report_path = _as_repo_path(repo_root, approval["source_convergence_report"])
    convergence_report = _PROMOTION_GATE.load_convergence_report(convergence_report_path)
    if convergence_report is None:
        raise ExecutionHandoffError(
            "candidate_execution_precondition_failed",
            f"convergence report missing for candidate {candidate_id}: {convergence_report_path}",
            findings=[
                _finding(
                    "candidate_execution_precondition_failed",
                    "deny",
                    str(convergence_report_path),
                    "convergence report missing for approved candidate",
                )
            ],
        )
    binding_findings = _PROMOTION_GATE.validate_approval_binding(
        approval,
        convergence_report,
        convergence_report_path,
    )
    candidate_binding_errors: list[dict[str, str]] = []
    if approval.get("evidence_ref") != candidate_id:
        candidate_binding_errors.append(
            _finding(
                "candidate_approval_binding_mismatch",
                "deny",
                "approval.evidence_ref",
                f"approval evidence_ref does not match candidate {candidate_id}",
            )
        )
    if _as_repo_path(repo_root, str(approval.get("source_convergence_report", ""))) != _as_repo_path(
        repo_root, str(candidate["source_convergence_report"])
    ):
        candidate_binding_errors.append(
            _finding(
                "candidate_approval_binding_mismatch",
                "deny",
                "approval.source_convergence_report",
                f"approval source_convergence_report does not match candidate {candidate_id}",
            )
        )
    for field, expected in (
        ("source_convergence_evidence_hash", candidate["source_convergence_evidence_hash"]),
        ("target_baseline_version", candidate["target_baseline_version"]),
        ("approval_scope", candidate["approval_scope"]),
    ):
        if approval.get(field) != expected:
            candidate_binding_errors.append(
                _finding(
                    "candidate_approval_binding_mismatch",
                    "deny",
                    f"approval.{field}",
                    f"approval field '{field}' does not match candidate {candidate_id}",
                )
            )
    if binding_findings or candidate_binding_errors:
        raise ExecutionHandoffError(
            "candidate_approval_binding_mismatch",
            f"approval binding mismatch for candidate {candidate_id}",
            findings=binding_findings + candidate_binding_errors,
        )
    active_state = load_current_active_state(repo_root)
    snapshot = _REGISTRY_CONSUMER.load_baseline_snapshot(_snapshot_path(repo_root))
    if snapshot is None:
        raise ExecutionHandoffError(
            "candidate_execution_precondition_failed",
            "baseline snapshot is missing before execution",
        )
    current_version = str(active_state["active_baseline_version"])
    target_version = str(candidate["target_baseline_version"])
    current_tuple = _parse_version(current_version)
    target_tuple = _parse_version(target_version)
    if current_tuple is None or target_tuple is None or target_tuple <= current_tuple:
        raise ExecutionHandoffError(
            "candidate_execution_precondition_failed",
            f"target version {target_version} must move forward from {current_version}",
        )
    pre_block_findings = _RELEASE_BLOCKER.validate_active_baseline_state(active_state)
    pre_block_findings.extend(_RELEASE_BLOCKER.validate_release_readiness(repo_root, active_state, snapshot))
    if pre_block_findings:
        raise ExecutionHandoffError(
            "candidate_execution_precondition_failed",
            "release readiness is not proven before execution handoff",
            findings=pre_block_findings,
        )
    return {
        "candidate": candidate,
        "approval": approval,
        "approval_path": approval_path,
        "convergence_report": convergence_report,
        "convergence_report_path": convergence_report_path,
        "baseline_snapshot": snapshot,
        "active_state": active_state,
    }


def _build_promotion_record(
    candidate: dict[str, Any],
    approval: dict[str, Any],
    convergence_report: dict[str, Any],
    convergence_report_path: Path,
    baseline_snapshot: dict[str, Any],
    promoted_snapshot: dict[str, Any],
) -> dict[str, Any]:
    baseline_sha256 = promoted_snapshot["baseline_sha256"]
    return {
        "promotion_id": f"PROMO-{uuid.uuid4().hex[:12].upper()}",
        "approved_at_utc": _utc_now_iso(),
        "approval_id": approval["approval_id"],
        "source_convergence_report": str(convergence_report_path),
        "source_convergence_evidence_hash": convergence_report["evidence_hash"],
        "previous_baseline_version": baseline_snapshot.get("baseline_version"),
        "promoted_baseline_version": candidate["target_baseline_version"],
        "decision": approval["decision"],
        "baseline_sha256": baseline_sha256,
        "promotion_evidence_hash": _json_sha256(
            {
                "approval_id": approval["approval_id"],
                "source_convergence_report": str(convergence_report_path),
                "source_convergence_evidence_hash": convergence_report["evidence_hash"],
                "promoted_baseline_version": candidate["target_baseline_version"],
                "baseline_sha256": baseline_sha256,
            }
        ),
    }


def refresh_active_state_after_promotion(repo_root: Path) -> dict[str, Any]:
    snapshot_path = _snapshot_path(repo_root)
    promotions_path = _promotions_path(repo_root)
    output_dir = _reports_dir(repo_root)
    snapshot = _REGISTRY_CONSUMER.load_baseline_snapshot(snapshot_path)
    records = _REGISTRY_CONSUMER.load_promotion_records(promotions_path)
    active_promotion, resolve_findings = _REGISTRY_CONSUMER.resolve_active_promotion(records)
    if snapshot is None or active_promotion is None or resolve_findings:
        raise ExecutionHandoffError(
            "active_state_refresh_failed",
            "unable to resolve active promotion after promotion write",
            findings=resolve_findings
            or [
                _finding(
                    "active_state_refresh_failed",
                    "deny",
                    str(promotions_path),
                    "active promotion could not be resolved",
                )
            ],
        )
    active_state = _REGISTRY_CONSUMER.build_active_baseline_state(
        snapshot,
        active_promotion,
        snapshot_path,
    )
    consistency_findings = _REGISTRY_CONSUMER.validate_registry_consistency(
        snapshot,
        active_promotion,
        active_state,
    )
    report = {
        "decision": "FAIL" if consistency_findings else "PASS",
        "mode": "refresh-active-state",
        "timestamp_utc": _utc_now_iso(),
        "active_state_path": str(_active_state_path(repo_root)),
        "active_baseline_state": active_state,
        "findings": consistency_findings,
        "evidence_hash": _json_sha256(
            {
                "active_state_path": str(_active_state_path(repo_root)),
                "active_baseline_version": active_state.get("active_baseline_version"),
                "source_promotion_id": active_state.get("source_promotion_id"),
            }
        ),
    }
    if consistency_findings:
        _REGISTRY_CONSUMER.emit_registry_consumption_report(report, output_dir)
        raise ExecutionHandoffError(
            "active_state_refresh_failed",
            "registry consistency failed after promotion",
            findings=consistency_findings,
        )
    try:
        _active_state_path(repo_root).write_text(
            json.dumps(active_state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        raise ExecutionHandoffError(
            "active_state_refresh_failed",
            f"failed to write active state: {exc}",
        ) from exc
    json_path, md_path = _REGISTRY_CONSUMER.emit_registry_consumption_report(report, output_dir)
    return {
        "decision": report["decision"],
        "active_state": active_state,
        "report_json": str(json_path),
        "report_md": str(md_path),
    }


def run_release_block_check(repo_root: Path) -> dict[str, Any]:
    output_dir = _reports_dir(repo_root)
    state_path = _active_state_path(repo_root)
    snapshot_path = _snapshot_path(repo_root)
    state = _RELEASE_BLOCKER.load_active_baseline_state(state_path)
    snapshot = _REGISTRY_CONSUMER.load_baseline_snapshot(snapshot_path)
    findings = _RELEASE_BLOCKER.validate_active_baseline_state(state)
    findings.extend(_RELEASE_BLOCKER.validate_release_readiness(repo_root, state, snapshot))
    report = {
        "decision": "FAIL" if findings else "PASS",
        "timestamp_utc": _utc_now_iso(),
        "active_state_path": str(state_path),
        "findings": findings,
        "evidence_hash": _json_sha256(
            {
                "active_state_path": str(state_path),
                "decision": "FAIL" if findings else "PASS",
            }
        ),
    }
    json_path, md_path = _RELEASE_BLOCKER.emit_release_block_report(report, output_dir)
    if findings:
        raise ExecutionHandoffError(
            "release_block_check_failed",
            "release blocker did not pass after promotion",
            findings=findings,
        )
    return {
        "decision": report["decision"],
        "report_json": str(json_path),
        "report_md": str(md_path),
    }


def emit_execution_result(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON_NAME
    md_path = output_dir / REPORT_MD_NAME
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# SoT Promotion Execution Result",
        "",
        "## Summary",
        "",
        f"- Candidate: `{result['candidate_id']}`",
        f"- Execution status: **{result['execution_status']}**",
        f"- Promotion ID: `{result.get('promotion_id')}`",
        f"- Approval file: `{result.get('approval_file')}`",
        f"- Promotion report: `{result.get('promotion_report')}`",
        f"- Active baseline after: `{result.get('active_baseline_version_after')}`",
        f"- Release block status: `{result.get('release_block_status')}`",
        f"- Execution history ID: `{result.get('execution_id')}`",
        "",
        "## Findings",
        "",
    ]
    findings = result.get("findings") or []
    if findings:
        for finding in findings:
            lines.append(
                f"- `{finding['finding_code']}` [{finding['severity']}] `{finding['path']}`: {finding['detail']}"
            )
    else:
        lines.append("- `none`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _write_history_or_raise(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return write_execution_history_record(repo_root, payload)
    except ExecutionHandoffError:
        raise
    except Exception as exc:
        raise ExecutionHandoffError(
            "execution_history_write_failed",
            f"failed to persist execution history: {exc}",
        ) from exc


def execute_promotion_handoff(repo_root: Path, candidate_id: str, executed_by: str, reason: str) -> dict[str, Any]:
    output_dir = _reports_dir(repo_root)
    context: dict[str, Any] | None = None
    try:
        context = validate_execution_preconditions(repo_root, candidate_id)
        candidate = context["candidate"]
        approval = context["approval"]
        approval_path = context["approval_path"]
        convergence_report = context["convergence_report"]
        convergence_report_path = context["convergence_report_path"]
        baseline_snapshot = context["baseline_snapshot"]
        try:
            evaluate_promotion_freeze_gate(
                repo_root,
                candidate_id=candidate_id,
                reason=reason,
            )
        except FreezeGovernanceError as exc:
            raise ExecutionHandoffError(
                exc.finding_code,
                str(exc),
                http_status=exc.http_status,
                findings=exc.findings,
            ) from exc
        evaluation = _PROMOTION_GATE.evaluate_promotion_gate(
            repo_root=repo_root,
            convergence_report=convergence_report,
            convergence_report_path=convergence_report_path,
            approval=approval,
            baseline_snapshot=baseline_snapshot,
            promote=True,
            verify_only=False,
        )
        if evaluation["decision"] != "PASS":
            raise ExecutionHandoffError(
                "promotion_execution_failed",
                "promotion gate did not return PASS during execute handoff",
                findings=evaluation["findings"],
            )
        promoted_snapshot = _PROMOTION_GATE.build_promoted_baseline_snapshot(
            baseline_snapshot=baseline_snapshot,
            approval=approval,
            approval_path=approval_path,
            convergence_report=convergence_report,
            convergence_report_path=convergence_report_path,
        )
        record = _build_promotion_record(
            candidate,
            approval,
            convergence_report,
            convergence_report_path,
            baseline_snapshot,
            promoted_snapshot,
        )
        try:
            promotion_record_path = _PROMOTION_GATE.write_promotion_record(_promotions_path(repo_root), record)
            _snapshot_path(repo_root).write_text(
                json.dumps(promoted_snapshot, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            raise ExecutionHandoffError(
                "promotion_execution_failed",
                f"promotion handoff failed during record or snapshot write: {exc}",
            ) from exc
        promotion_report = {
            "run_metadata": {
                "executed_by": executed_by,
                "reason": reason,
            },
            "decision": "PASS",
            "mode": "promote",
            "timestamp_utc": _utc_now_iso(),
            "repo_root": str(repo_root),
            "evidence_hash": record["promotion_evidence_hash"],
            "convergence_input": {
                "path": str(convergence_report_path),
                "present": True,
            },
            "approval_input": {
                "path": str(approval_path),
                "present": True,
                "approval_id": approval["approval_id"],
                "approval_scope": approval["approval_scope"],
            },
            "binding_result": {
                "binding_valid": True,
                "findings": [],
            },
            "findings": [],
            "previous_baseline_version": baseline_snapshot.get("baseline_version"),
            "target_baseline_version": approval["target_baseline_version"],
            "promotion_record_path": str(promotion_record_path),
            "resulting_baseline": promoted_snapshot,
        }
        promotion_report_json, _ = _PROMOTION_GATE.emit_promotion_report(promotion_report, output_dir)
        refreshed = refresh_active_state_after_promotion(repo_root)
        blocker = run_release_block_check(repo_root)
        try:
            _OPERATOR_APPROVAL.append_candidate_status(
                _candidate_registry_path(repo_root),
                candidate,
                "promoted",
            )
        except Exception as exc:
            raise ExecutionHandoffError(
                "candidate_status_update_failed",
                f"failed to update candidate status to promoted: {exc}",
            ) from exc
        history_record = _write_history_or_raise(
            repo_root,
            {
                "executed_by": executed_by,
                "candidate_id": candidate_id,
                "approval_id": approval["approval_id"],
                "promotion_id": record["promotion_id"],
                "baseline_version_before": baseline_snapshot.get("baseline_version"),
                "baseline_version_after": candidate["target_baseline_version"],
                "release_block_status_after": blocker["decision"],
                "execution_status": "PASS",
                "reason": reason,
                "approval_file": str(approval_path),
                "promotion_report": str(promotion_report_json),
            },
        )
        result = {
            "candidate_id": candidate_id,
            "execution_id": history_record["execution_id"],
            "execution_status": "PASS",
            "promotion_id": record["promotion_id"],
            "approval_file": str(approval_path),
            "promotion_report": str(promotion_report_json),
            "active_baseline_version_after": refreshed["active_state"]["active_baseline_version"],
            "release_block_status": blocker["decision"],
            "findings": [],
        }
        execution_json, execution_md = emit_execution_result(result, output_dir)
        result["execution_report_json"] = str(execution_json)
        result["execution_report_md"] = str(execution_md)
        return result
    except ExecutionHandoffError as exc:
        history_id: str | None = None
        if context is not None:
            candidate = context["candidate"]
            approval = context["approval"]
            approval_path = context["approval_path"]
            baseline_snapshot = context["baseline_snapshot"]
            try:
                history_record = _write_history_or_raise(
                    repo_root,
                    {
                        "executed_by": executed_by,
                        "candidate_id": candidate_id,
                        "approval_id": approval["approval_id"],
                        "promotion_id": None,
                        "baseline_version_before": baseline_snapshot.get("baseline_version"),
                        "baseline_version_after": candidate.get("target_baseline_version"),
                        "release_block_status_after": "FAIL",
                        "execution_status": "FAIL",
                        "reason": reason,
                        "approval_file": str(approval_path),
                        "promotion_report": None,
                    },
                )
                history_id = history_record["execution_id"]
            except ExecutionHandoffError as history_exc:
                combined_findings = exc.findings + history_exc.findings
                raise ExecutionHandoffError(
                    "execution_history_write_failed",
                    str(history_exc),
                    findings=combined_findings,
                ) from history_exc
        result = {
            "candidate_id": candidate_id,
            "execution_id": history_id,
            "execution_status": "FAIL",
            "promotion_id": None,
            "approval_file": None,
            "promotion_report": None,
            "active_baseline_version_after": None,
            "release_block_status": "FAIL",
            "findings": exc.findings,
        }
        emit_execution_result(result, output_dir)
        raise
