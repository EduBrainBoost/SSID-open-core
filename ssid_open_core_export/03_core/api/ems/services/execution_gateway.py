from pathlib import Path
from typing import Any

from ems.services.execution_gate_decider import evaluate_execution_gate
from ems.services.execution_lifecycle_store import (
    append_execution_run_record,
    get_execution_run,
    list_execution_runs,
)
from ems.services.execution_runtime_context import build_execution_runtime_context
from ems.services.sot_promotion_execution_service import execute_promotion_handoff


def evaluate_execution_run(
    *,
    repo_root: Path,
    execution_target: str,
    target_id: str,
    requested_by: str,
    reason: str,
) -> dict[str, Any]:
    context = build_execution_runtime_context(
        repo_root=repo_root,
        execution_target=execution_target,
        target_id=target_id,
        requested_by=requested_by,
        reason=reason,
    )
    decision = evaluate_execution_gate(context)
    return {
        "decision": decision["decision"],
        "blocker_codes": decision["blocker_codes"],
        "context": {
            "execution_target": context.execution_target,
            "target_id": context.target_id,
            "freeze_level": context.freeze_level,
            "release_block_status": context.release_block_status,
            "runtime_dependency_status": context.runtime_dependency_status,
            "approval_status": context.approval_status,
            "active_run_id": context.active_run_id,
        },
    }


def start_execution_run(
    *,
    repo_root: Path,
    execution_target: str,
    target_id: str,
    requested_by: str,
    reason: str,
) -> dict[str, Any]:
    evaluation = evaluate_execution_run(
        repo_root=repo_root,
        execution_target=execution_target,
        target_id=target_id,
        requested_by=requested_by,
        reason=reason,
    )
    if evaluation["decision"] != "PASS":
        run = append_execution_run_record(
            repo_root,
            {
                "execution_target": execution_target,
                "target_id": target_id,
                "status": "blocked",
                "decision": evaluation["decision"],
                "blocker_codes": evaluation["blocker_codes"],
                "requested_by": requested_by,
                "reason": reason,
            },
        )
        return {
            "decision": evaluation["decision"],
            "blocker_codes": evaluation["blocker_codes"],
            "run": run,
            "handoff": None,
        }

    if execution_target != "promotion":
        raise ValueError(f"unsupported_execution_target: {execution_target}")

    handoff = execute_promotion_handoff(repo_root, target_id, requested_by, reason)
    run = append_execution_run_record(
        repo_root,
        {
            "execution_target": execution_target,
            "target_id": target_id,
            "status": "succeeded" if handoff.get("execution_status") == "PASS" else "failed",
            "decision": "PASS" if handoff.get("execution_status") == "PASS" else "BLOCK",
            "blocker_codes": [],
            "requested_by": requested_by,
            "reason": reason,
            "handoff_execution_id": handoff.get("execution_id"),
            "handoff_status": handoff.get("execution_status"),
        },
    )
    return {
        "decision": "PASS",
        "blocker_codes": [],
        "run": run,
        "handoff": handoff,
    }


def list_gateway_runs(repo_root: Path) -> list[dict[str, Any]]:
    return list_execution_runs(repo_root)


def get_gateway_run(repo_root: Path, run_id: str) -> dict[str, Any]:
    return get_execution_run(repo_root, run_id)


def get_execution_live_status(repo_root: Path) -> dict[str, Any]:
    runs = list_execution_runs(repo_root)
    latest = runs[0] if runs else None
    return {
        "decision": latest.get("decision", "UNKNOWN") if latest else "UNKNOWN",
        "latest_run": latest,
        "active_blockers": list(latest.get("blocker_codes", [])) if latest else [],
        "run_count": len(runs),
    }


def get_execution_blockers(repo_root: Path) -> dict[str, Any]:
    live_status = get_execution_live_status(repo_root)
    return {"blocker_codes": live_status["active_blockers"]}


def defer_execution_run(
    *,
    repo_root: Path,
    execution_target: str,
    target_id: str,
    requested_by: str,
    reason: str,
) -> dict[str, Any]:
    run = append_execution_run_record(
        repo_root,
        {
            "execution_target": execution_target,
            "target_id": target_id,
            "status": "deferred",
            "decision": "DEFER",
            "blocker_codes": [],
            "requested_by": requested_by,
            "reason": reason,
        },
    )
    return {"decision": "DEFER", "blocker_codes": [], "run": run, "handoff": None}


def abort_execution_run(
    *,
    repo_root: Path,
    execution_target: str,
    target_id: str,
    requested_by: str,
    reason: str,
) -> dict[str, Any]:
    run = append_execution_run_record(
        repo_root,
        {
            "execution_target": execution_target,
            "target_id": target_id,
            "status": "aborted",
            "decision": "ABORT",
            "blocker_codes": [],
            "requested_by": requested_by,
            "reason": reason,
        },
    )
    return {"decision": "ABORT", "blocker_codes": [], "run": run, "handoff": None}
