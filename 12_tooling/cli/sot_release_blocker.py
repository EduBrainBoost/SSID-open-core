#!/usr/bin/env python3
"""Fail-closed release blocker for active baseline state."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 2

DEFAULT_OUTPUT_REL = "02_audit_logging/reports"
DEFAULT_ACTIVE_STATE_REL = "24_meta_orchestration/registry/sot_active_baseline_state.json"
DEFAULT_BASELINE_REL = "24_meta_orchestration/registry/sot_baseline_snapshot.json"
REPORT_JSON = "sot_release_block_report.json"
REPORT_MD = "sot_release_block_report.md"

ACTIVE_STATE_REQUIRED_FIELDS = (
    "state_id",
    "updated_at_utc",
    "active_baseline_version",
    "baseline_snapshot_path",
    "baseline_snapshot_sha256",
    "source_promotion_id",
    "source_approval_id",
    "source_convergence_report",
    "source_convergence_evidence_hash",
    "decision",
    "scope",
    "consistency_status",
    "evidence_hash",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _snapshot_sha(snapshot: dict) -> str:
    embedded = snapshot.get("baseline_sha256") if isinstance(snapshot, dict) else None
    if isinstance(embedded, str) and embedded:
        return embedded
    return _json_sha256(snapshot)


def _finding(code: str, severity: str, path: str, detail: str) -> dict[str, str]:
    return {"finding_code": code, "severity": severity, "path": path, "detail": detail}


def load_active_baseline_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def validate_active_baseline_state(state: dict | None) -> list[dict[str, str]]:
    if state is None:
        return [_finding("active_baseline_state_missing", "deny", DEFAULT_ACTIVE_STATE_REL, "active baseline state is missing or unreadable")]
    findings: list[dict[str, str]] = []
    missing = [field for field in ACTIVE_STATE_REQUIRED_FIELDS if field not in state]
    if missing:
        findings.append(_finding("active_baseline_state_invalid", "deny", DEFAULT_ACTIVE_STATE_REL, f"active baseline state missing required fields: {missing}"))
    expected_hash = _json_sha256({k: v for k, v in state.items() if k != "evidence_hash"})
    if state.get("evidence_hash") != expected_hash:
        findings.append(_finding("active_baseline_state_invalid", "deny", DEFAULT_ACTIVE_STATE_REL, "active baseline state evidence_hash is invalid"))
    return findings


def validate_release_readiness(repo_root: Path, state: dict | None, snapshot: dict | None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if state is None:
        return [_finding("release_readiness_not_proven", "deny", str(repo_root), "release readiness cannot be proven without active baseline state")]
    if not state.get("source_approval_id"):
        findings.append(_finding("approval_binding_missing", "deny", "source_approval_id", "source_approval_id is required to prove approval binding"))
    if not state.get("source_convergence_report") or not state.get("source_convergence_evidence_hash"):
        findings.append(_finding("convergence_binding_missing", "deny", "source_convergence_report", "convergence report path and evidence hash are required to prove convergence binding"))
    if snapshot is None:
        findings.append(_finding("release_readiness_not_proven", "deny", DEFAULT_BASELINE_REL, "baseline snapshot missing or unreadable"))
        return findings
    snapshot_sha = _snapshot_sha(snapshot)
    if state.get("baseline_snapshot_sha256") != snapshot_sha:
        findings.append(_finding("release_readiness_not_proven", "deny", "baseline_snapshot_sha256", "active state snapshot hash does not match the current baseline snapshot"))
    if state.get("active_baseline_version") != snapshot.get("baseline_version"):
        findings.append(_finding("release_readiness_not_proven", "deny", "active_baseline_version", "active baseline version does not match the current baseline snapshot version"))
    if state.get("consistency_status") != "CONSISTENT":
        findings.append(_finding("release_readiness_not_proven", "deny", "consistency_status", "consistency_status must be CONSISTENT"))
    if state.get("decision") != "approve":
        findings.append(_finding("release_readiness_not_proven", "deny", "decision", "decision must be approve for release readiness"))
    return findings


def emit_release_block_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON
    md_path = output_dir / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# SoT Release Block Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Decision | **{report['decision']}** |",
        f"| Timestamp | {report['timestamp_utc']} |",
        f"| Active State | `{report['active_state_path']}` |",
        f"| Evidence Hash | `{report['evidence_hash']}` |",
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
    parser = argparse.ArgumentParser(prog="sot_release_blocker.py")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--active-state-file", required=True)
    parser.add_argument("--check", action="store_true", required=False)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    output_dir = (repo_root / DEFAULT_OUTPUT_REL).resolve()
    active_state_path = Path(args.active_state_file).resolve()
    baseline_path = repo_root / DEFAULT_BASELINE_REL
    state = load_active_baseline_state(active_state_path)
    snapshot = None
    if baseline_path.exists():
        try:
            snapshot = json.loads(baseline_path.read_text(encoding="utf-8"))
        except Exception:
            snapshot = None

    findings = validate_active_baseline_state(state)
    findings.extend(validate_release_readiness(repo_root, state, snapshot))
    decision = "FAIL" if any(item["severity"] == "deny" for item in findings) else "PASS"
    if decision == "FAIL":
        findings.append(_finding("release_block_fail_closed", "deny", str(repo_root), "release blocker failed closed because release readiness could not be proven"))

    report = {
        "audit_type": "sot_release_blocker",
        "timestamp_utc": _utc_now_iso(),
        "repo_root": str(repo_root),
        "active_state_path": str(active_state_path),
        "decision": decision,
        "findings": findings,
        "finding_codes": [item["finding_code"] for item in findings],
        "evidence_hash": "",
    }
    report["evidence_hash"] = _json_sha256({k: v for k, v in report.items() if k != "evidence_hash"})
    emit_release_block_report(report, output_dir)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        print((output_dir / REPORT_MD).read_text(encoding="utf-8"))
    else:
        print(f"SoT Release Blocker: {decision}")
        print(f"  Findings: {len(findings)}")
        print(f"  Report: {output_dir / REPORT_JSON}")

    return EXIT_FAIL if decision == "FAIL" else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
