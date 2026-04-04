import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ems.services.sot_incident_freeze_governance import (
    FreezeGovernanceError,
    evaluate_recovery_freeze_gate,
)
from ems.services.sot_promotion_execution_service import (
    _REGISTRY_CONSUMER,
    ExecutionHandoffError,
    _active_state_path,
    _json_sha256,
    _promotions_path,
    _snapshot_path,
    run_release_block_check,
)
from ems.services.sot_promotion_service import _read_jsonl, load_active_baseline_state
from ems.services.sot_rollback_proposal_service import (
    get_rollback_proposal,
    mark_rollback_proposal_status,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _recovery_history_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_rollback_recovery_history.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def _load_execution_history(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "24_meta_orchestration" / "registry" / "sot_promotion_execution_history.jsonl"
    return _read_jsonl(path)


def load_approved_rollback_proposal(repo_root: Path, proposal_id: str) -> dict[str, Any]:
    proposal = get_rollback_proposal(repo_root, proposal_id)
    if proposal.get("status") != "approved":
        raise ExecutionHandoffError(
            "rollback_recovery_not_approved",
            f"rollback proposal {proposal_id} has status '{proposal.get('status')}', expected approved",
            http_status=409,
        )
    return proposal


def validate_recovery_preconditions(repo_root: Path, proposal_id: str) -> dict[str, Any]:
    proposal = load_approved_rollback_proposal(repo_root, proposal_id)
    active_state = load_active_baseline_state(repo_root)
    if active_state["active_baseline_version"] != proposal["current_active_version"]:
        raise ExecutionHandoffError(
            "rollback_recovery_precondition_failed",
            "current active baseline no longer matches proposal source state",
        )

    history = _load_execution_history(repo_root)
    source_match = None
    for item in history:
        if item.get("execution_id") == proposal["source_execution_id"]:
            source_match = item
    if source_match is None:
        raise ExecutionHandoffError(
            "rollback_recovery_precondition_failed",
            "required execution history for rollback recovery is missing",
        )
    if source_match.get("baseline_version_before") != proposal["target_baseline_version"]:
        raise ExecutionHandoffError(
            "rollback_recovery_precondition_failed",
            "rollback recovery only supports immediate predecessor target versions",
        )
    return {
        "proposal": proposal,
        "active_state": active_state,
        "source_history": source_match,
    }


def write_recovery_history_record(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    record.setdefault("recovery_id", f"REC-{uuid.uuid4().hex[:12].upper()}")
    record.setdefault("executed_at_utc", _utc_now_iso())
    record["recovery_evidence_hash"] = _json_sha256({k: v for k, v in record.items() if k != "recovery_evidence_hash"})
    try:
        _append_jsonl(_recovery_history_path(repo_root), record)
    except Exception as exc:
        raise ExecutionHandoffError(
            "rollback_recovery_history_write_failed",
            f"failed to write rollback recovery history: {exc}",
        ) from exc
    return record


def refresh_active_state_after_recovery(repo_root: Path) -> dict[str, Any]:
    try:
        snapshot_path = _snapshot_path(repo_root)
        snapshot = _REGISTRY_CONSUMER.load_baseline_snapshot(snapshot_path)
        records = _read_jsonl(_promotions_path(repo_root))
        if snapshot is None or not records:
            raise ExecutionHandoffError(
                "rollback_recovery_active_state_refresh_failed",
                "recovery refresh cannot resolve snapshot or promotion records",
            )
        active_promotion = records[-1]
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
        if consistency_findings:
            raise ExecutionHandoffError(
                "rollback_recovery_active_state_refresh_failed",
                "registry consistency failed after recovery",
                findings=consistency_findings,
            )
        _active_state_path(repo_root).write_text(
            json.dumps(active_state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return {
            "decision": "PASS",
            "active_state": active_state,
        }
    except ExecutionHandoffError as exc:
        raise ExecutionHandoffError(
            "rollback_recovery_active_state_refresh_failed",
            str(exc),
            findings=exc.findings,
        ) from exc


def run_release_block_check_after_recovery(repo_root: Path) -> dict[str, Any]:
    try:
        return run_release_block_check(repo_root)
    except ExecutionHandoffError as exc:
        raise ExecutionHandoffError(
            "rollback_recovery_release_block_failed",
            str(exc),
            findings=exc.findings,
        ) from exc


def execute_guarded_recovery_handoff(
    repo_root: Path,
    proposal_id: str,
    executed_by: str,
    reason: str,
) -> dict[str, Any]:
    context = validate_recovery_preconditions(repo_root, proposal_id)
    proposal = context["proposal"]
    active_state = context["active_state"]
    try:
        evaluate_recovery_freeze_gate(
            repo_root,
            operation_type="rollback_execute",
            proposal_id=proposal_id,
            target_baseline_version=str(proposal["target_baseline_version"]),
            reason=reason,
        )
    except FreezeGovernanceError as exc:
        raise ExecutionHandoffError(
            exc.finding_code,
            str(exc),
            http_status=exc.http_status,
            findings=exc.findings,
        ) from exc

    try:
        snapshot = json.loads(_snapshot_path(repo_root).read_text(encoding="utf-8"))
        promotions = _read_jsonl(_promotions_path(repo_root))
    except Exception as exc:
        raise ExecutionHandoffError(
            "rollback_recovery_execution_failed",
            f"failed to load recovery prerequisites: {exc}",
        ) from exc

    matched_promotion = None
    for record in promotions:
        if record.get("promoted_baseline_version") == proposal["target_baseline_version"]:
            matched_promotion = record
    if matched_promotion is None:
        raise ExecutionHandoffError(
            "rollback_recovery_execution_failed",
            "no matching promotion record found for rollback target",
        )

    updated_snapshot = dict(snapshot)
    updated_snapshot["baseline_version"] = proposal["target_baseline_version"]
    updated_snapshot["promotion"] = {
        "approval_id": matched_promotion["approval_id"],
        "source_convergence_report": matched_promotion["source_convergence_report"],
        "source_convergence_evidence_hash": matched_promotion["source_convergence_evidence_hash"],
        "decision": matched_promotion["decision"],
        "approval_scope": "canonical_sot",
        "evidence_ref": proposal_id,
    }
    updated_snapshot["baseline_sha256"] = _json_sha256(updated_snapshot)

    recovery_promotion_record = {
        "promotion_id": f"PROMO-RBK-{uuid.uuid4().hex[:8].upper()}",
        "approved_at_utc": _utc_now_iso(),
        "approval_id": f"RBK-{proposal_id}",
        "source_convergence_report": matched_promotion["source_convergence_report"],
        "source_convergence_evidence_hash": matched_promotion["source_convergence_evidence_hash"],
        "previous_baseline_version": active_state["active_baseline_version"],
        "promoted_baseline_version": proposal["target_baseline_version"],
        "decision": "approve",
        "baseline_sha256": updated_snapshot["baseline_sha256"],
        "promotion_evidence_hash": _json_sha256(
            {
                "proposal_id": proposal_id,
                "baseline_version_after": proposal["target_baseline_version"],
                "baseline_sha256": updated_snapshot["baseline_sha256"],
            }
        ),
    }

    try:
        with _promotions_path(repo_root).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(recovery_promotion_record, sort_keys=True, ensure_ascii=False) + "\n")
        _snapshot_path(repo_root).write_text(
            json.dumps(updated_snapshot, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        raise ExecutionHandoffError(
            "rollback_recovery_execution_failed",
            f"failed to persist guarded recovery state: {exc}",
        ) from exc

    refresh_active_state_after_recovery(repo_root)
    blocker = run_release_block_check_after_recovery(repo_root)
    try:
        mark_rollback_proposal_status(
            repo_root,
            {k: v for k, v in proposal.items() if k != "history"},
            "executed",
        )
    except Exception as exc:
        raise ExecutionHandoffError(
            "rollback_recovery_status_update_failed",
            f"failed to update rollback proposal status: {exc}",
        ) from exc

    history = write_recovery_history_record(
        repo_root,
        {
            "executed_by": executed_by,
            "proposal_id": proposal_id,
            "baseline_version_before": active_state["active_baseline_version"],
            "baseline_version_after": proposal["target_baseline_version"],
            "release_block_status_after": blocker["decision"],
            "recovery_status": "PASS",
            "reason": reason,
        },
    )
    return {
        "recovery_id": history["recovery_id"],
        "recovery_status": "PASS",
        "baseline_version_after": proposal["target_baseline_version"],
        "release_block_status_after": blocker["decision"],
        "findings": [],
    }
