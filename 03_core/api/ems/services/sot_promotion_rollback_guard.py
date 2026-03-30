import json
from pathlib import Path
from typing import Any

from ems.services.sot_promotion_service import (
    RegistryConsistencyError,
    _read_json,
    _read_jsonl,
    load_active_baseline_state,
)


def _execution_history_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "sot_promotion_execution_history.jsonl"


def _release_block_report_path(repo_root: Path) -> Path:
    return repo_root / "02_audit_logging" / "reports" / "sot_release_block_report.json"


def _parse_version(version: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in version.split("."))
    except Exception:
        return None


def _finding(finding_code: str, severity: str, path: str, detail: str) -> dict[str, str]:
    return {
        "finding_code": finding_code,
        "severity": severity,
        "path": path,
        "detail": detail,
    }


def _fail(
    current_active_version: str | None,
    target_baseline_version: str,
    findings: list[dict[str, str]],
) -> dict[str, Any]:
    if not any(item["finding_code"] == "rollback_guard_fail_closed" for item in findings):
        findings.append(
            _finding(
                "rollback_guard_fail_closed",
                "deny",
                "rollback",
                "rollback evaluation failed closed",
            )
        )
    return {
        "allowed": False,
        "guard_decision": "FAIL",
        "current_active_version": current_active_version,
        "target_baseline_version": target_baseline_version,
        "findings": findings,
    }


def evaluate_rollback_guard(
    repo_root: Path,
    requested_by: str,
    target_baseline_version: str,
    reason: str,
) -> dict[str, Any]:
    del requested_by
    try:
        active_state = load_active_baseline_state(repo_root)
    except Exception as exc:
        return _fail(
            None,
            target_baseline_version,
            [
                _finding(
                    "rollback_active_state_invalid",
                    "deny",
                    "active_state",
                    str(exc),
                )
            ],
        )

    current_version = str(active_state["active_baseline_version"])
    findings: list[dict[str, str]] = []
    if not reason.strip():
        findings.append(
            _finding(
                "rollback_reason_missing",
                "deny",
                "request.reason",
                "rollback evaluation requires a reason",
            )
        )
    if active_state.get("consistency_status") != "CONSISTENT":
        findings.append(
            _finding(
                "rollback_active_state_invalid",
                "deny",
                "active_state.consistency_status",
                "active state must be CONSISTENT before rollback evaluation",
            )
        )

    current_tuple = _parse_version(current_version)
    target_tuple = _parse_version(target_baseline_version)
    if target_baseline_version == current_version:
        findings.append(
            _finding(
                "rollback_same_version_forbidden",
                "deny",
                "request.target_baseline_version",
                "rollback target must differ from the current active version",
            )
        )
    elif current_tuple is None or target_tuple is None or target_tuple >= current_tuple:
        findings.append(
            _finding(
                "rollback_target_not_older",
                "deny",
                "request.target_baseline_version",
                "rollback target must be older than the current active version",
            )
        )

    try:
        release_report = _read_json(_release_block_report_path(repo_root))
        if release_report.get("decision") != "PASS":
            findings.append(
                _finding(
                    "rollback_release_state_invalid",
                    "deny",
                    "release_block_report",
                    "latest release blocker state must be PASS for rollback evaluation",
                )
            )
    except Exception as exc:
        findings.append(
            _finding(
                "rollback_release_state_invalid",
                "deny",
                "release_block_report",
                str(exc),
            )
        )

    try:
        history = _read_jsonl(_execution_history_path(repo_root))
    except FileNotFoundError:
        findings.append(
            _finding(
                "rollback_target_missing",
                "deny",
                "execution_history",
                "execution history is missing",
            )
        )
        return _fail(current_version, target_baseline_version, findings)
    except (json.JSONDecodeError, RegistryConsistencyError) as exc:
        findings.append(
            _finding(
                "rollback_history_binding_missing",
                "deny",
                "execution_history",
                str(exc),
            )
        )
        return _fail(current_version, target_baseline_version, findings)

    successful = [item for item in history if item.get("execution_status") == "PASS"]
    if not successful:
        findings.append(
            _finding(
                "rollback_target_missing",
                "deny",
                "execution_history",
                "no successful execution history exists for rollback evaluation",
            )
        )
        return _fail(current_version, target_baseline_version, findings)

    matching_target = [
        item
        for item in successful
        if item.get("baseline_version_before") == target_baseline_version
        or item.get("baseline_version_after") == target_baseline_version
    ]
    if not matching_target:
        findings.append(
            _finding(
                "rollback_target_missing",
                "deny",
                "request.target_baseline_version",
                "requested rollback target does not exist in promotion execution history",
            )
        )
        return _fail(current_version, target_baseline_version, findings)

    latest_success = successful[-1]
    if latest_success.get("baseline_version_before") != target_baseline_version:
        findings.append(
            _finding(
                "rollback_history_binding_missing",
                "deny",
                "execution_history",
                "rollback evaluation only allows the immediate predecessor baseline version",
            )
        )

    if findings:
        return _fail(current_version, target_baseline_version, findings)

    return {
        "allowed": True,
        "guard_decision": "PASS",
        "current_active_version": current_version,
        "target_baseline_version": target_baseline_version,
        "findings": [],
    }
