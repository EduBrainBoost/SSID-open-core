import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ems.services.sot_promotion_execution_service import (
    list_execution_history,
    validate_rollback_guard,
)
from ems.services.sot_promotion_service import (
    RegistryConsistencyError,
    _read_jsonl,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _proposal_registry_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_rollback_proposals.jsonl"


def _proposal_decisions_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_rollback_operator_decisions.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def _latest(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        proposal_id = record.get("proposal_id")
        if not proposal_id:
            raise RegistryConsistencyError("rollback proposal record missing proposal_id")
        latest[proposal_id] = record
    return latest


def list_rollback_proposals(repo_root: Path, status: str | None = None) -> list[dict[str, Any]]:
    path = _proposal_registry_path(repo_root)
    if not path.exists():
        return []
    items = list(_latest(_read_jsonl(path)).values())
    items.sort(key=lambda item: item.get("created_at_utc", ""))
    if status is None:
        return items
    return [item for item in items if item.get("status") == status]


def get_rollback_proposal(repo_root: Path, proposal_id: str) -> dict[str, Any]:
    path = _proposal_registry_path(repo_root)
    if not path.exists():
        raise FileNotFoundError(f"rollback_proposal_not_found: {proposal_id}")
    records = _read_jsonl(path)
    history = [item for item in records if item.get("proposal_id") == proposal_id]
    if not history:
        raise FileNotFoundError(f"rollback_proposal_not_found: {proposal_id}")
    detail = dict(history[-1])
    detail["history"] = history
    return detail


def append_rollback_proposal(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    record.setdefault("proposal_id", f"RBP-{uuid.uuid4().hex[:12].upper()}")
    record.setdefault("created_at_utc", _utc_now_iso())
    record["proposal_evidence_hash"] = _json_sha256(
        {k: v for k, v in record.items() if k != "proposal_evidence_hash"}
    )
    try:
        _append_jsonl(_proposal_registry_path(repo_root), record)
    except Exception as exc:
        raise RuntimeError(f"rollback_proposal_write_failed: {exc}") from exc
    return record


def mark_rollback_proposal_status(repo_root: Path, proposal: dict[str, Any], status: str) -> dict[str, Any]:
    payload = dict(proposal)
    payload["status"] = status
    payload["history"] = proposal.get("history", [])
    return append_rollback_proposal(repo_root, payload)


def _latest_successful_execution_for_current_version(
    repo_root: Path,
    current_active_version: str,
) -> dict[str, Any] | None:
    history = list_execution_history(repo_root)
    successful = [item for item in history if item.get("execution_status") == "PASS"]
    for item in reversed(successful):
        if item.get("baseline_version_after") == current_active_version:
            return item
    return successful[-1] if successful else None


def evaluate_and_build_rollback_proposal(
    repo_root: Path,
    created_by: str,
    target_baseline_version: str,
    reason: str,
) -> dict[str, Any]:
    guard = validate_rollback_guard(repo_root, created_by, target_baseline_version, reason)
    if not guard["allowed"]:
        raise ValueError(f"rollback_proposal_guard_failed: {guard['guard_decision']}")

    current_active_version = str(guard["current_active_version"])
    existing = list_rollback_proposals(repo_root, status="pending")
    for item in existing:
        if (
            item.get("current_active_version") == current_active_version
            and item.get("target_baseline_version") == target_baseline_version
        ):
            raise ValueError(
                "rollback_proposal_already_exists: matching pending proposal already exists"
            )

    source_execution = _latest_successful_execution_for_current_version(repo_root, current_active_version)
    if source_execution is None:
        raise ValueError("rollback_proposal_guard_failed: no source execution found")

    proposal = append_rollback_proposal(
        repo_root,
        {
            "created_by": created_by,
            "source_execution_id": source_execution["execution_id"],
            "current_active_version": current_active_version,
            "target_baseline_version": target_baseline_version,
            "guard_decision": guard["guard_decision"],
            "guard_allowed": guard["allowed"],
            "reason": reason,
            "status": "pending",
        },
    )
    return {
        "proposal_id": proposal["proposal_id"],
        "guard_decision": proposal["guard_decision"],
        "guard_allowed": proposal["guard_allowed"],
        "status": proposal["status"],
        "current_active_version": proposal["current_active_version"],
        "target_baseline_version": proposal["target_baseline_version"],
    }


def _append_operator_decision(
    repo_root: Path,
    proposal_id: str,
    decided_by: str,
    decision: str,
    reason: str,
) -> dict[str, Any]:
    payload = {
        "decision_id": f"RBD-{uuid.uuid4().hex[:12].upper()}",
        "proposal_id": proposal_id,
        "decided_at_utc": _utc_now_iso(),
        "decided_by": decided_by,
        "decision": decision,
        "reason": reason,
    }
    payload["decision_evidence_hash"] = _json_sha256(payload)
    try:
        _append_jsonl(_proposal_decisions_path(repo_root), payload)
    except Exception as exc:
        raise RuntimeError(f"rollback_operator_decision_write_failed: {exc}") from exc
    return payload


def decide_rollback_proposal(
    repo_root: Path,
    proposal_id: str,
    decided_by: str,
    decision: str,
    reason: str,
) -> dict[str, Any]:
    proposal = get_rollback_proposal(repo_root, proposal_id)
    if proposal.get("status") != "pending":
        raise ValueError(f"rollback_proposal_not_pending: {proposal_id}")
    _append_operator_decision(repo_root, proposal_id, decided_by, decision, reason)
    updated = mark_rollback_proposal_status(
        repo_root,
        {k: v for k, v in proposal.items() if k != "history"},
        "approved" if decision == "approve" else "rejected",
    )
    return {
        "decision": decision,
        "proposal_id": proposal_id,
        "status_after": updated["status"],
    }
