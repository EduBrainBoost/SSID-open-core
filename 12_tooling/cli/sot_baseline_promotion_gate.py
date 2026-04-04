#!/usr/bin/env python3
"""Baseline Promotion Approval Gate — CC-SSID-GATE-02."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_cli_dir = str(Path(__file__).resolve().parent)
if _cli_dir not in sys.path:
    sys.path.insert(0, _cli_dir)

from cross_artifact_reference_audit import AuditResult, Finding  # noqa: E402
from sot_baseline_gate import DEFAULT_BASELINE_REL, load_baseline_snapshot  # noqa: E402

EXIT_PASS = 0
EXIT_FAIL = 2

DEFAULT_OUTPUT_REL = "02_audit_logging/reports"
DEFAULT_CONVERGENCE_REL = "02_audit_logging/reports/reference_gates_convergence_report.json"
DEFAULT_PROMOTIONS_REL = "24_meta_orchestration/registry/sot_baseline_promotions.jsonl"
DEFAULT_APPROVAL_EXAMPLE_REL = "02_audit_logging/reports/sot_baseline_promotion_approval.example.json"
APPROVAL_SCHEMA_REL = "16_codex/contracts/sot/sot_baseline_promotion_approval.schema.json"
ALLOWED_APPROVAL_SCOPES = {"canonical_sot", "full_canonical_sot"}
REPORT_JSON_NAME = "sot_baseline_promotion_report.json"
REPORT_MD_NAME = "sot_baseline_promotion_report.md"

APPROVAL_REQUIRED_FIELDS = (
    "approval_id",
    "created_at_utc",
    "approved_by",
    "reason",
    "source_convergence_report",
    "source_convergence_evidence_hash",
    "source_baseline_snapshot",
    "target_baseline_version",
    "approval_scope",
    "decision",
    "evidence_ref",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _detect_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_version(version: str) -> tuple[int, int, int] | None:
    parts = str(version).split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _finding(code: str, severity: str, path: str, detail: str) -> dict[str, str]:
    return {
        "finding_code": code,
        "severity": severity,
        "path": path,
        "detail": detail,
    }


def _add_finding(result: AuditResult, finding: dict[str, str]) -> None:
    result.add(Finding(finding["finding_code"], finding["severity"], finding["path"], finding["detail"]))


def load_convergence_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    required = {"report_type", "final_decision", "evidence_hash", "timestamp_utc"}
    if not isinstance(data, dict) or not required.issubset(data.keys()):
        return None
    return data


def load_promotion_approval(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def validate_approval_schema(approval: dict | None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(approval, dict):
        return [
            _finding("promotion_approval_schema_invalid", "deny", "approval", "approval payload is not a JSON object")
        ]

    missing = [field for field in APPROVAL_REQUIRED_FIELDS if field not in approval]
    if missing:
        findings.append(
            _finding(
                "promotion_approval_schema_invalid",
                "deny",
                "approval",
                f"approval missing required fields: {missing}",
            )
        )

    created = approval.get("created_at_utc")
    if created is not None:
        try:
            datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except ValueError:
            findings.append(
                _finding(
                    "promotion_approval_schema_invalid",
                    "deny",
                    "approval.created_at_utc",
                    f"created_at_utc is not valid ISO8601 UTC: {created}",
                )
            )

    decision = approval.get("decision")
    if decision not in {"approve", "reject"}:
        findings.append(
            _finding(
                "promotion_approval_schema_invalid",
                "deny",
                "approval.decision",
                f"decision must be 'approve' or 'reject', got '{decision}'",
            )
        )

    evidence_hash = approval.get("source_convergence_evidence_hash")
    if evidence_hash is not None and (
        not isinstance(evidence_hash, str)
        or len(evidence_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in evidence_hash)
    ):
        findings.append(
            _finding(
                "promotion_approval_schema_invalid",
                "deny",
                "approval.source_convergence_evidence_hash",
                "source_convergence_evidence_hash must be a lowercase SHA256 hex digest",
            )
        )

    target_version = approval.get("target_baseline_version")
    if target_version is not None and _parse_version(str(target_version)) is None:
        findings.append(
            _finding(
                "target_baseline_version_invalid",
                "deny",
                "approval.target_baseline_version",
                f"target_baseline_version is not strict semver X.Y.Z: {target_version}",
            )
        )

    return findings


def validate_approval_binding(
    approval: dict,
    convergence_report: dict,
    convergence_report_path: Path,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected_report = str(convergence_report_path)
    actual_report = str(approval.get("source_convergence_report", ""))
    if actual_report != expected_report:
        findings.append(
            _finding(
                "promotion_binding_mismatch",
                "deny",
                "approval.source_convergence_report",
                f"source_convergence_report does not exactly match the checked report: approval='{actual_report}' checked='{expected_report}'",
            )
        )
    if approval.get("source_convergence_evidence_hash") != convergence_report.get("evidence_hash"):
        findings.append(
            _finding(
                "promotion_binding_mismatch",
                "deny",
                "approval.source_convergence_evidence_hash",
                "source_convergence_evidence_hash does not match the checked convergence report evidence hash",
            )
        )
    return findings


def evaluate_promotion_gate(
    *,
    repo_root: Path,
    convergence_report: dict | None,
    convergence_report_path: Path,
    approval: dict | None,
    baseline_snapshot: dict | None,
    promote: bool,
    verify_only: bool,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    binding_findings: list[dict[str, str]] = []
    previous_version = baseline_snapshot.get("baseline_version") if isinstance(baseline_snapshot, dict) else None
    target_version = approval.get("target_baseline_version") if isinstance(approval, dict) else None

    if convergence_report is None:
        findings.append(
            _finding(
                "convergence_report_missing",
                "deny",
                str(convergence_report_path),
                "convergence report is missing or unreadable",
            )
        )
    else:
        required = {"report_type", "final_decision", "evidence_hash", "timestamp_utc"}
        missing = sorted(required - set(convergence_report.keys()))
        if missing:
            findings.append(
                _finding(
                    "convergence_report_invalid",
                    "deny",
                    str(convergence_report_path),
                    f"convergence report missing required fields: {missing}",
                )
            )
        elif convergence_report.get("final_decision") != "PASS":
            findings.append(
                _finding(
                    "convergence_not_pass",
                    "deny",
                    str(convergence_report_path),
                    f"convergence report final_decision is '{convergence_report.get('final_decision')}', only PASS is promotable",
                )
            )

    if approval is None:
        findings.append(
            _finding("promotion_approval_missing", "deny", "approval", "promotion approval is missing or unreadable")
        )
    else:
        findings.extend(validate_approval_schema(approval))
        if approval.get("decision") == "reject":
            findings.append(
                _finding(
                    "promotion_approval_rejected",
                    "deny",
                    "approval.decision",
                    "approval decision is reject; promotion is blocked",
                )
            )
        scope = approval.get("approval_scope")
        if scope not in ALLOWED_APPROVAL_SCOPES:
            findings.append(
                _finding(
                    "promotion_scope_mismatch",
                    "deny",
                    "approval.approval_scope",
                    f"approval_scope '{scope}' is not allowed; expected one of {sorted(ALLOWED_APPROVAL_SCOPES)}",
                )
            )
        if convergence_report is not None:
            binding_findings = validate_approval_binding(approval, convergence_report, convergence_report_path)
            findings.extend(binding_findings)

    if previous_version is not None and target_version is not None:
        previous_tuple = _parse_version(str(previous_version))
        target_tuple = _parse_version(str(target_version))
        if previous_tuple is None or target_tuple is None or target_tuple <= previous_tuple:
            findings.append(
                _finding(
                    "target_baseline_version_invalid",
                    "deny",
                    "approval.target_baseline_version",
                    f"target_baseline_version '{target_version}' must move strictly forward from '{previous_version}'",
                )
            )

    decision = "FAIL" if any(item["severity"] == "deny" for item in findings) else "PASS"
    if decision == "PASS" and verify_only:
        findings.append(
            _finding(
                "promotion_preview_only",
                "warn",
                "promotion_gate",
                "verify-only mode validated the promotion path but performed no mutation",
            )
        )
        decision = "WARN"

    if decision == "FAIL":
        findings.append(
            _finding(
                "promotion_fail_closed",
                "deny",
                str(repo_root),
                "promotion gate failed closed due to one or more blocking inconsistencies",
            )
        )

    return {
        "decision": decision,
        "findings": findings,
        "finding_codes": [item["finding_code"] for item in findings],
        "binding_findings": binding_findings,
        "binding_valid": not binding_findings,
        "previous_baseline_version": previous_version,
        "target_baseline_version": target_version,
        "promotion_allowed": decision == "PASS" and promote and not verify_only,
    }


def build_promoted_baseline_snapshot(
    *,
    baseline_snapshot: dict,
    approval: dict,
    approval_path: Path,
    convergence_report: dict,
    convergence_report_path: Path,
) -> dict[str, Any]:
    promoted = json.loads(json.dumps(baseline_snapshot))
    promoted["snapshot_id"] = f"BL-{_utc_now_iso()}"
    promoted["created_at_utc"] = _utc_now_iso()
    promoted["baseline_version"] = approval["target_baseline_version"]
    promoted["generator"] = "sot_baseline_promotion_gate.py"
    promoted["promotion"] = {
        "approval_id": approval["approval_id"],
        "approval_path": str(approval_path),
        "approved_by": approval["approved_by"],
        "source_convergence_report": str(convergence_report_path),
        "source_convergence_evidence_hash": convergence_report["evidence_hash"],
        "approval_scope": approval["approval_scope"],
        "decision": approval["decision"],
        "evidence_ref": approval["evidence_ref"],
    }
    promoted["evidence_hash"] = _json_sha256(
        {
            "baseline_version": promoted["baseline_version"],
            "artifacts": promoted["artifacts"],
            "promotion": promoted["promotion"],
        }
    )
    promoted["baseline_sha256"] = _json_sha256(promoted)
    return promoted


def write_promotion_record(promotions_path: Path, record: dict[str, Any]) -> Path:
    promotions_path.parent.mkdir(parents=True, exist_ok=True)
    with promotions_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return promotions_path


def emit_promotion_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON_NAME
    md_path = output_dir / REPORT_MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines: list[str] = [
        "# SoT Baseline Promotion Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Decision | **{report['decision']}** |",
        f"| Mode | `{report['mode']}` |",
        f"| Timestamp | {report['timestamp_utc']} |",
        f"| Repo | `{report['repo_root']}` |",
        f"| Evidence Hash | `{report['evidence_hash']}` |",
        "",
        "## Approval Validation",
        "",
        f"- Approval file: `{report['approval_input']['path']}`",
        f"- Approval present: `{report['approval_input']['present']}`",
        f"- Approval ID: `{report['approval_input'].get('approval_id')}`",
        f"- Approval scope: `{report['approval_input'].get('approval_scope')}`",
        "",
        "## Binding Validation",
        "",
        f"- Convergence report: `{report['convergence_input']['path']}`",
        f"- Binding valid: `{report['binding_result']['binding_valid']}`",
        "",
        "## Promotion Decision",
        "",
        f"- Previous baseline: `{report['previous_baseline_version']}`",
        f"- Target baseline: `{report['target_baseline_version']}`",
        f"- Promotion record path: `{report['promotion_record_path']}`",
        "",
        "## Findings Table",
        "",
        "| # | Code | Severity | Path | Detail |",
        "|---|------|----------|------|--------|",
    ]
    for index, finding in enumerate(report["findings"], start=1):
        lines.append(
            f"| {index} | `{finding['finding_code']}` | {finding['severity']} | `{finding['path']}` | {finding['detail']} |"
        )
    if not report["findings"]:
        lines.append("| 1 | `none` | info | `-` | No findings |")
    lines.extend(
        [
            "",
            "## Resulting Baseline Info",
            "",
            f"- Result baseline version: `{report['resulting_baseline'].get('baseline_version')}`",
            f"- Result baseline sha256: `{report['resulting_baseline'].get('baseline_sha256')}`",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def _build_report(
    *,
    repo_root: Path,
    mode: str,
    convergence_report_path: Path,
    convergence_report: dict | None,
    approval_path: Path,
    approval: dict | None,
    evaluation: dict[str, Any],
    promotion_record_path: Path | None,
    promoted_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    report_body = {
        "audit_type": "sot_baseline_promotion_gate",
        "timestamp_utc": _utc_now_iso(),
        "repo_root": str(repo_root),
        "mode": mode,
        "convergence_input": {
            "path": str(convergence_report_path),
            "present": convergence_report is not None,
            "final_decision": convergence_report.get("final_decision") if convergence_report else None,
            "evidence_hash": convergence_report.get("evidence_hash") if convergence_report else None,
        },
        "approval_input": {
            "path": str(approval_path),
            "present": approval is not None,
            "approval_id": approval.get("approval_id") if approval else None,
            "approval_scope": approval.get("approval_scope") if approval else None,
            "decision": approval.get("decision") if approval else None,
        },
        "binding_result": {
            "binding_valid": evaluation["binding_valid"],
            "findings": evaluation["binding_findings"],
        },
        "decision": evaluation["decision"],
        "findings": evaluation["findings"],
        "finding_codes": evaluation["finding_codes"],
        "previous_baseline_version": evaluation["previous_baseline_version"],
        "target_baseline_version": evaluation["target_baseline_version"],
        "promotion_record_path": str(promotion_record_path) if promotion_record_path else None,
        "evidence_hash": "",
        "resulting_baseline": {
            "baseline_version": promoted_snapshot.get("baseline_version")
            if promoted_snapshot
            else evaluation["previous_baseline_version"],
            "baseline_sha256": promoted_snapshot.get("baseline_sha256") if promoted_snapshot else None,
        },
    }
    report_body["evidence_hash"] = _json_sha256(report_body)
    return report_body


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sot_baseline_promotion_gate.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--promote", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--convergence-report", required=True)
    parser.add_argument("--approval-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    convergence_report_path = Path(args.convergence_report).resolve()
    approval_path = Path(args.approval_file).resolve()
    output_dir = Path(args.output_dir).resolve()
    mode = "promote" if args.promote else "verify-only" if args.verify_only else "check"

    baseline_path = repo_root / DEFAULT_BASELINE_REL
    promotions_path = repo_root / DEFAULT_PROMOTIONS_REL

    convergence_report = load_convergence_report(convergence_report_path)
    approval = load_promotion_approval(approval_path)
    baseline_snapshot = load_baseline_snapshot(baseline_path)

    evaluation = evaluate_promotion_gate(
        repo_root=repo_root,
        convergence_report=convergence_report,
        convergence_report_path=convergence_report_path,
        approval=approval,
        baseline_snapshot=baseline_snapshot,
        promote=args.promote,
        verify_only=args.verify_only,
    )

    result = AuditResult()
    for finding in evaluation["findings"]:
        _add_finding(result, finding)

    promotion_record_path: Path | None = None
    promoted_snapshot: dict[str, Any] | None = None

    if args.promote and evaluation["decision"] == "PASS":
        promoted_snapshot = build_promoted_baseline_snapshot(
            baseline_snapshot=baseline_snapshot,
            approval=approval,
            approval_path=approval_path,
            convergence_report=convergence_report,
            convergence_report_path=convergence_report_path,
        )
        baseline_sha256 = promoted_snapshot["baseline_sha256"]
        record = {
            "promotion_id": f"PROMO-{uuid.uuid4().hex[:12].upper()}",
            "approved_at_utc": _utc_now_iso(),
            "approval_id": approval["approval_id"],
            "source_convergence_report": str(convergence_report_path),
            "source_convergence_evidence_hash": convergence_report["evidence_hash"],
            "previous_baseline_version": baseline_snapshot.get("baseline_version") if baseline_snapshot else None,
            "promoted_baseline_version": approval["target_baseline_version"],
            "decision": approval["decision"],
            "baseline_sha256": baseline_sha256,
            "promotion_evidence_hash": _json_sha256(
                {
                    "approval_id": approval["approval_id"],
                    "source_convergence_report": str(convergence_report_path),
                    "source_convergence_evidence_hash": convergence_report["evidence_hash"],
                    "promoted_baseline_version": approval["target_baseline_version"],
                    "baseline_sha256": baseline_sha256,
                }
            ),
        }
        try:
            promotion_record_path = write_promotion_record(promotions_path, record)
        except Exception as exc:
            finding = _finding(
                "promotion_record_write_failed",
                "deny",
                str(promotions_path),
                f"failed to append promotion record: {exc}",
            )
            evaluation["decision"] = "FAIL"
            evaluation["findings"].append(finding)
            evaluation["finding_codes"].append(finding["finding_code"])
            _add_finding(result, finding)
            fail_closed = _finding(
                "promotion_fail_closed",
                "deny",
                str(repo_root),
                "promotion gate failed closed after promotion record write failure",
            )
            evaluation["findings"].append(fail_closed)
            evaluation["finding_codes"].append(fail_closed["finding_code"])
            _add_finding(result, fail_closed)
        else:
            try:
                baseline_path.write_text(
                    json.dumps(promoted_snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            except Exception as exc:
                finding = _finding(
                    "baseline_snapshot_update_failed",
                    "deny",
                    str(baseline_path),
                    f"failed to update promoted baseline snapshot: {exc}",
                )
                evaluation["decision"] = "FAIL"
                evaluation["findings"].append(finding)
                evaluation["finding_codes"].append(finding["finding_code"])
                _add_finding(result, finding)
                fail_closed = _finding(
                    "promotion_fail_closed",
                    "deny",
                    str(repo_root),
                    "promotion gate failed closed after baseline snapshot update failure",
                )
                evaluation["findings"].append(fail_closed)
                evaluation["finding_codes"].append(fail_closed["finding_code"])
                _add_finding(result, fail_closed)

    report = _build_report(
        repo_root=repo_root,
        mode=mode,
        convergence_report_path=convergence_report_path,
        convergence_report=convergence_report,
        approval_path=approval_path,
        approval=approval,
        evaluation=evaluation,
        promotion_record_path=promotion_record_path,
        promoted_snapshot=promoted_snapshot,
    )
    emit_promotion_report(report, output_dir)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        print((output_dir / REPORT_MD_NAME).read_text(encoding="utf-8"))
    else:
        print(f"SoT Baseline Promotion Gate: {evaluation['decision']}")
        print(f"  Mode: {mode}")
        print(f"  Findings: {len(evaluation['findings'])}")
        print(f"  Report: {output_dir / REPORT_JSON_NAME}")

    return EXIT_FAIL if evaluation["decision"] == "FAIL" else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
