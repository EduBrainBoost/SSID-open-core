import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ems.services.execution_lifecycle_store import list_execution_runs
from ems.services.sot_incident_freeze_governance import load_freeze_state
from ems.services.sot_promotion_service import get_candidate, list_operator_approvals


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _release_block_path(repo_root: Path) -> Path:
    return repo_root / "02_audit_logging" / "reports" / "sot_release_block_report.json"


def _shards_registry_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "shards_registry.json"


def _approval_status(repo_root: Path, target_id: str) -> str:
    candidate = get_candidate(repo_root, target_id)
    if candidate.get("status") != "approved":
        return str(candidate.get("status") or "missing")
    approvals = list_operator_approvals(repo_root)
    for item in reversed(approvals):
        if item.get("candidate_id") == target_id and item.get("decision") == "approve":
            return "approved" if item.get("approval_file") else "missing"
    return "missing"


def _runtime_dependency_status(repo_root: Path) -> str:
    registry = _read_json(_shards_registry_path(repo_root))
    for shard in registry.get("shards", []):
        service_status = str(shard.get("service_runtime_status", "unknown"))
        dependency_status = str(shard.get("dependency_status", "unknown"))
        if service_status != "ready":
            return "FAIL"
        if dependency_status not in {"ready", "n/a"}:
            return "FAIL"
    return "PASS"


def _active_run(repo_root: Path, execution_target: str, target_id: str) -> dict[str, Any] | None:
    active_statuses = {"evaluated", "gated", "executing", "deferred"}
    for item in list_execution_runs(repo_root):
        if (
            item.get("execution_target") == execution_target
            and item.get("target_id") == target_id
            and item.get("status") in active_statuses
        ):
            return item
    return None


@dataclass(frozen=True)
class ExecutionRuntimeContext:
    repo_root: Path
    execution_target: str
    target_id: str
    requested_by: str
    reason: str
    freeze_level: str
    release_block_status: str
    runtime_dependency_status: str
    approval_status: str
    active_run_id: str | None = None
    active_run_status: str | None = None


def build_execution_runtime_context(
    *,
    repo_root: Path,
    execution_target: str,
    target_id: str,
    requested_by: str,
    reason: str,
) -> ExecutionRuntimeContext:
    freeze_state = load_freeze_state(repo_root)
    release_report = _read_json(_release_block_path(repo_root))
    active_run = _active_run(repo_root, execution_target, target_id)
    return ExecutionRuntimeContext(
        repo_root=repo_root,
        execution_target=execution_target,
        target_id=target_id,
        requested_by=requested_by,
        reason=reason,
        freeze_level=str(freeze_state.get("freeze_level", "unknown")),
        release_block_status=str(release_report.get("decision", "FAIL")),
        runtime_dependency_status=_runtime_dependency_status(repo_root),
        approval_status=_approval_status(repo_root, target_id),
        active_run_id=active_run.get("run_id") if active_run else None,
        active_run_status=active_run.get("status") if active_run else None,
    )
