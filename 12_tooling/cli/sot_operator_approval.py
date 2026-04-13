#!/usr/bin/env python3
"""Operator approval workflow for promotion candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 2

DEFAULT_CANDIDATE_REGISTRY = "24_meta_orchestration/registry/sot_promotion_candidates.jsonl"
DEFAULT_APPROVAL_LOG = "24_meta_orchestration/registry/sot_operator_approvals.jsonl"
DEFAULT_OUTPUT_REL = "02_audit_logging/reports"
DEFAULT_BASELINE_REL = "24_meta_orchestration/registry/sot_baseline_snapshot.json"
REPORT_JSON = "sot_operator_approval_report.json"
REPORT_MD = "sot_operator_approval_report.md"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _finding(code: str, severity: str, path: str, detail: str) -> dict[str, str]:
    return {"finding_code": code, "severity": severity, "path": path, "detail": detail}


def load_candidate_registry(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _latest_candidate_states(records: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        if candidate_id:
            latest[candidate_id] = record
    return latest


def resolve_candidate(records: list[dict], candidate_id: str) -> tuple[dict | None, list[dict[str, str]]]:
    if not records:
        return None, [_finding("candidate_registry_missing", "deny", DEFAULT_CANDIDATE_REGISTRY, "candidate registry is missing or empty")]
    latest = _latest_candidate_states(records)
    record = latest.get(candidate_id)
    if record is not None:
        if record.get("status") != "pending":
            return None, [_finding("candidate_not_pending", "deny", candidate_id, f"candidate status is '{record.get('status')}', expected pending")]
        return record, []
    return None, [_finding("candidate_not_found", "deny", candidate_id, "candidate_id not found in registry")]


def build_approval_from_candidate(candidate: dict, approved_by: str, reason: str, repo_root: Path, output_dir: Path) -> tuple[dict, Path]:
    approval = {
        "approval_id": f"APR-{candidate['candidate_id']}",
        "created_at_utc": _utc_now_iso(),
        "approved_by": approved_by,
        "reason": reason,
        "source_convergence_report": candidate["source_convergence_report"],
        "source_convergence_evidence_hash": candidate["source_convergence_evidence_hash"],
        "source_baseline_snapshot": DEFAULT_BASELINE_REL,
        "target_baseline_version": candidate["target_baseline_version"],
        "approval_scope": candidate["approval_scope"],
        "decision": "approve",
        "evidence_ref": candidate["candidate_id"],
    }
    approval_path = output_dir / f"sot_baseline_promotion_approval.{candidate['candidate_id']}.json"
    return approval, approval_path


def append_operator_decision(path: Path, decision: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(decision, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def append_candidate_status(path: Path, candidate: dict[str, Any], status: str) -> Path:
    updated = dict(candidate)
    updated["status"] = status
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(updated, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def emit_operator_approval_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON
    md_path = output_dir / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# SoT Operator Approval Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Decision | **{report['decision']}** |",
        f"| Action | `{report['action']}` |",
        f"| Candidate ID | `{report['candidate_id']}` |",
        "",
        "## Findings",
        "",
        "| # | Code | Severity | Path | Detail |",
        "|---|------|----------|------|--------|",
    ]
    if report["findings"]:
        for index, finding in enumerate(report["findings"], start=1):
            lines.append(f"| {index} | `{finding['finding_code']}` | {finding['severity']} | `{finding['path']}` | {finding['detail']} |")
    else:
        lines.append("| 1 | `none` | info | `-` | No findings |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sot_operator_approval.py")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--list-pending", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--reject", action="store_true")
    parser.add_argument("--candidate-id")
    parser.add_argument("--approved-by")
    parser.add_argument("--reason")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    candidate_registry = repo_root / DEFAULT_CANDIDATE_REGISTRY
    approval_log = repo_root / DEFAULT_APPROVAL_LOG
    records = load_candidate_registry(candidate_registry)
    findings: list[dict[str, str]] = []
    action = "list-pending" if args.list_pending else "approve" if args.approve else "reject" if args.reject else "invalid"
    pending = [record for record in _latest_candidate_states(records).values() if record.get("status") == "pending"]
    approval_file_path: Path | None = None
    decision_log_entry: dict[str, Any] | None = None

    if args.list_pending:
        decision = "PASS"
    else:
        if not args.approve and not args.reject:
            findings.append(_finding("operator_decision_invalid", "deny", "action", "either --approve or --reject is required"))
        if not args.candidate_id:
            findings.append(_finding("candidate_not_found", "deny", "candidate_id", "candidate_id is required"))
        if not args.approved_by:
            findings.append(_finding("operator_identity_missing", "deny", "approved_by", "approved_by is required"))
        if findings:
            decision = "FAIL"
        else:
            candidate, resolve_findings = resolve_candidate(records, args.candidate_id)
            findings.extend(resolve_findings)
            decision = "FAIL" if findings else "PASS"
            if decision == "PASS":
                if args.approve:
                    approval_payload, approval_file_path = build_approval_from_candidate(candidate, args.approved_by, args.reason or candidate["reason"], repo_root, output_dir)
                    try:
                        approval_file_path.write_text(json.dumps(approval_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    except Exception as exc:
                        findings.append(_finding("approval_artifact_write_failed", "deny", str(approval_file_path), f"failed to write approval artifact: {exc}"))
                        decision = "FAIL"
                decision_log_entry = {
                    "decision_id": f"DEC-{uuid.uuid4().hex[:12].upper()}",
                    "candidate_id": candidate["candidate_id"],
                    "decided_at_utc": _utc_now_iso(),
                    "decided_by": args.approved_by,
                    "decision": "approve" if args.approve else "reject",
                    "reason": args.reason or candidate["reason"],
                    "approval_file": str(approval_file_path) if approval_file_path else None,
                    "decision_evidence_hash": "",
                }
                decision_log_entry["decision_evidence_hash"] = _json_sha256({k: v for k, v in decision_log_entry.items() if k != "decision_evidence_hash"})
                if decision == "PASS":
                    try:
                        append_operator_decision(approval_log, decision_log_entry)
                        append_candidate_status(
                            candidate_registry,
                            candidate,
                            "approved" if args.approve else "rejected",
                        )
                    except Exception as exc:
                        findings.append(_finding("operator_approval_log_write_failed", "deny", str(approval_log), f"failed to append operator decision: {exc}"))
                        decision = "FAIL"

    if decision == "FAIL":
        findings.append(_finding("operator_approval_fail_closed", "deny", str(repo_root), "operator approval workflow failed closed due to blocking inconsistencies"))

    report = {
        "audit_type": "sot_operator_approval",
        "timestamp_utc": _utc_now_iso(),
        "repo_root": str(repo_root),
        "action": action,
        "decision": decision,
        "candidate_id": args.candidate_id,
        "pending_candidates": pending,
        "approval_file": str(approval_file_path) if approval_file_path else None,
        "decision_log_entry": decision_log_entry,
        "findings": findings,
        "finding_codes": [item["finding_code"] for item in findings],
        "evidence_hash": "",
    }
    report["evidence_hash"] = _json_sha256({k: v for k, v in report.items() if k != "evidence_hash"})
    emit_operator_approval_report(report, output_dir)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        print((output_dir / REPORT_MD).read_text(encoding="utf-8"))
    else:
        print(f"SoT Operator Approval: {decision}")
        print(f"  Action: {action}")
        print(f"  Findings: {len(findings)}")
        print(f"  Report: {output_dir / REPORT_JSON}")
    return EXIT_FAIL if decision == "FAIL" else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
