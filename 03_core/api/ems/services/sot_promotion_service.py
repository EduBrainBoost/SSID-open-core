import hashlib
import importlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CLI_ROOT = _PROJECT_ROOT / "12_tooling" / "cli"
if str(_CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLI_ROOT))

_OPERATOR_APPROVAL = importlib.import_module("sot_operator_approval")


class RegistryConsistencyError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required registry file missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryConsistencyError(f"Invalid JSON in {path}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Required registry file missing: {path}")
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RegistryConsistencyError(f"Invalid JSONL record in {path}") from exc
        if not isinstance(payload, dict):
            raise RegistryConsistencyError(f"Invalid JSONL object in {path}")
        items.append(payload)
    return items


def _registry_path(repo_root: Path, relative: str) -> Path:
    return repo_root / relative


def _latest_candidate_states(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        if not candidate_id:
            raise RegistryConsistencyError("Candidate registry record missing candidate_id")
        latest[candidate_id] = record
    return latest


def _candidate_history(records: list[dict[str, Any]], candidate_id: str) -> list[dict[str, Any]]:
    return [record for record in records if record.get("candidate_id") == candidate_id]


def _decision_log_path(repo_root: Path) -> Path:
    return _registry_path(repo_root, "24_meta_orchestration/registry/sot_operator_approvals.jsonl")


def _candidate_registry_path(repo_root: Path) -> Path:
    return _registry_path(repo_root, "24_meta_orchestration/registry/sot_promotion_candidates.jsonl")


def _active_state_path(repo_root: Path) -> Path:
    return _registry_path(repo_root, "24_meta_orchestration/registry/sot_active_baseline_state.json")


def _snapshot_path(repo_root: Path) -> Path:
    return _registry_path(repo_root, "24_meta_orchestration/registry/sot_baseline_snapshot.json")


def _snapshot_sha(snapshot: dict[str, Any]) -> str:
    embedded = snapshot.get("baseline_sha256")
    if isinstance(embedded, str) and embedded:
        return embedded
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _json_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_active_baseline_state(repo_root: Path) -> dict[str, Any]:
    state = _read_json(_active_state_path(repo_root))
    required = {
        "active_baseline_version",
        "baseline_snapshot_path",
        "baseline_snapshot_sha256",
        "source_promotion_id",
        "source_approval_id",
        "source_convergence_report",
        "source_convergence_evidence_hash",
        "decision",
        "consistency_status",
        "updated_at_utc",
    }
    missing = sorted(required - set(state))
    if missing:
        raise RegistryConsistencyError(f"Active baseline state missing fields: {', '.join(missing)}")

    snapshot = _read_json(_snapshot_path(repo_root))
    if snapshot.get("baseline_version") != state["active_baseline_version"]:
        raise RegistryConsistencyError("Active baseline version does not match snapshot version")
    if _snapshot_sha(snapshot) != state["baseline_snapshot_sha256"]:
        raise RegistryConsistencyError("Active baseline state does not match snapshot hash")
    return state


def list_candidates(repo_root: Path, status: str | None = None) -> list[dict[str, Any]]:
    latest = list(_latest_candidate_states(_read_jsonl(_candidate_registry_path(repo_root))).values())
    latest.sort(key=lambda item: item.get("created_at_utc", ""))
    if status is None:
        return latest
    return [item for item in latest if item.get("status") == status]


def get_candidate(repo_root: Path, candidate_id: str) -> dict[str, Any]:
    records = _read_jsonl(_candidate_registry_path(repo_root))
    latest = _latest_candidate_states(records).get(candidate_id)
    if latest is None:
        raise FileNotFoundError(f"Candidate not found: {candidate_id}")
    detail = dict(latest)
    detail["history"] = _candidate_history(records, candidate_id)
    return detail


def list_operator_approvals(repo_root: Path) -> list[dict[str, Any]]:
    items = _read_jsonl(_decision_log_path(repo_root))
    items.sort(key=lambda item: item.get("decided_at_utc", ""))
    return items


def _write_approval_artifact(repo_root: Path, candidate_id: str, approval_payload: dict[str, Any]) -> str:
    reports_dir = repo_root / "02_audit_logging" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    approval_path = reports_dir / f"sot_baseline_promotion_approval.{candidate_id}.json"
    approval_path.write_text(json.dumps(approval_payload, indent=2), encoding="utf-8")
    return str(approval_path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def approve_candidate(repo_root: Path, candidate_id: str, approved_by: str, reason: str) -> dict[str, Any]:
    candidate = get_candidate(repo_root, candidate_id)
    if candidate.get("status") != "pending":
        raise ValueError(f"Candidate is not pending: {candidate_id}")

    output_dir = repo_root / "02_audit_logging" / "reports"
    approval_payload, approval_path = _OPERATOR_APPROVAL.build_approval_from_candidate(
        candidate,
        approved_by=approved_by,
        reason=reason,
        repo_root=repo_root,
        output_dir=output_dir,
    )
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps(approval_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    approval_file = str(approval_path)

    decision_payload = {
        "decision_id": f"DEC-{uuid.uuid4().hex[:12].upper()}",
        "candidate_id": candidate_id,
        "decided_at_utc": _utc_now(),
        "decided_by": approved_by,
        "decision": "approve",
        "reason": reason,
        "approval_file": approval_file,
        "decision_evidence_hash": "",
    }
    decision_payload["decision_evidence_hash"] = _json_sha256(
        {k: v for k, v in decision_payload.items() if k != "decision_evidence_hash"}
    )
    _OPERATOR_APPROVAL.append_operator_decision(_decision_log_path(repo_root), decision_payload)
    _OPERATOR_APPROVAL.append_candidate_status(_candidate_registry_path(repo_root), candidate, "approved")

    return {
        "decision": "approve",
        "candidate_id": candidate_id,
        "approval_file": approval_file,
        "status_after": "approved",
        "decision_id": decision_payload["decision_id"],
    }


def reject_candidate(repo_root: Path, candidate_id: str, approved_by: str, reason: str) -> dict[str, Any]:
    candidate = get_candidate(repo_root, candidate_id)
    if candidate.get("status") != "pending":
        raise ValueError(f"Candidate is not pending: {candidate_id}")

    decision_payload = {
        "decision_id": f"DEC-{uuid.uuid4().hex[:12].upper()}",
        "candidate_id": candidate_id,
        "decided_at_utc": _utc_now(),
        "decided_by": approved_by,
        "decision": "reject",
        "reason": reason,
        "approval_file": None,
        "decision_evidence_hash": "",
    }
    decision_payload["decision_evidence_hash"] = _json_sha256(
        {k: v for k, v in decision_payload.items() if k != "decision_evidence_hash"}
    )
    _OPERATOR_APPROVAL.append_operator_decision(_decision_log_path(repo_root), decision_payload)
    _OPERATOR_APPROVAL.append_candidate_status(_candidate_registry_path(repo_root), candidate, "rejected")

    return {
        "decision": "reject",
        "candidate_id": candidate_id,
        "approval_file": None,
        "status_after": "rejected",
        "decision_id": decision_payload["decision_id"],
    }
