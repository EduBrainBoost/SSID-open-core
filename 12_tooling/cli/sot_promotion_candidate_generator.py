#!/usr/bin/env python3
"""Generate promotion candidates from a PASS convergence state."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 2

DEFAULT_CANDIDATE_REGISTRY = "24_meta_orchestration/registry/sot_promotion_candidates.jsonl"
DEFAULT_OUTPUT_REL = "02_audit_logging/reports"
REPORT_JSON = "sot_promotion_candidate_report.json"
REPORT_MD = "sot_promotion_candidate_report.md"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _parse_version(version: str) -> tuple[int, int, int] | None:
    parts = str(version).split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _finding(code: str, severity: str, path: str, detail: str) -> dict[str, str]:
    return {"finding_code": code, "severity": severity, "path": path, "detail": detail}


def load_convergence_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_active_baseline_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def derive_candidate_version(active_version: str) -> str | None:
    parsed = _parse_version(active_version)
    if parsed is None:
        return None
    major, minor, patch = parsed
    return f"{major}.{minor}.{patch + 1}"


def build_promotion_candidate(
    *,
    convergence_report: dict,
    convergence_report_path: Path,
    active_state: dict,
    reason: str,
    approval_scope: str,
) -> dict[str, Any]:
    target_version = derive_candidate_version(active_state["active_baseline_version"])
    candidate = {
        "candidate_id": f"CAND-{_utc_now_iso().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:6].upper()}",
        "created_at_utc": _utc_now_iso(),
        "status": "pending",
        "source_convergence_report": str(convergence_report_path),
        "source_convergence_evidence_hash": convergence_report["evidence_hash"],
        "source_active_baseline_version": active_state["active_baseline_version"],
        "target_baseline_version": target_version,
        "approval_scope": approval_scope,
        "reason": reason,
        "candidate_evidence_hash": "",
    }
    candidate["candidate_evidence_hash"] = _json_sha256(
        {k: v for k, v in candidate.items() if k != "candidate_evidence_hash"}
    )
    return candidate


def write_candidate_record(path: Path, candidate: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(candidate, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def emit_candidate_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON
    md_path = output_dir / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# SoT Promotion Candidate Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Decision | **{report['decision']}** |",
        f"| Mode | `{report['mode']}` |",
        f"| Candidate ID | `{report.get('candidate', {}).get('candidate_id') if report.get('candidate') else None}` |",
        "",
        "## Findings",
        "",
        "| # | Code | Severity | Path | Detail |",
        "|---|------|----------|------|--------|",
    ]
    if report["findings"]:
        for index, finding in enumerate(report["findings"], start=1):
            lines.append(
                f"| {index} | `{finding['finding_code']}` | {finding['severity']} | `{finding['path']}` | {finding['detail']} |"
            )
    else:
        lines.append("| 1 | `none` | info | `-` | No findings |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def _load_candidate_registry(path: Path) -> list[dict]:
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sot_promotion_candidate_generator.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--convergence-report", required=True)
    parser.add_argument("--active-state-file", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--approval-scope", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    convergence_path = Path(args.convergence_report).resolve()
    active_state_path = Path(args.active_state_file).resolve()
    output_dir = Path(args.output_dir).resolve()
    registry_path = repo_root / DEFAULT_CANDIDATE_REGISTRY
    mode = "generate" if args.generate else "verify-only" if args.verify_only else "check"

    findings: list[dict[str, str]] = []
    report = load_convergence_report(convergence_path)
    if report is None:
        findings.append(
            _finding(
                "convergence_report_missing", "deny", str(convergence_path), "convergence report missing or unreadable"
            )
        )
    elif report.get("final_decision") != "PASS":
        findings.append(
            _finding(
                "convergence_not_pass",
                "deny",
                str(convergence_path),
                f"convergence final_decision is '{report.get('final_decision')}', expected PASS",
            )
        )

    active_state = load_active_baseline_state(active_state_path)
    if active_state is None:
        findings.append(
            _finding(
                "active_baseline_state_missing",
                "deny",
                str(active_state_path),
                "active baseline state missing or unreadable",
            )
        )
    else:
        required = {
            "active_baseline_version",
            "decision",
            "consistency_status",
            "source_convergence_report",
            "source_convergence_evidence_hash",
        }
        missing = sorted(required - set(active_state.keys()))
        if (
            missing
            or active_state.get("decision") != "approve"
            or active_state.get("consistency_status") != "CONSISTENT"
        ):
            findings.append(
                _finding(
                    "active_baseline_state_invalid",
                    "deny",
                    str(active_state_path),
                    f"active state invalid for candidate generation; missing={missing} decision={active_state.get('decision')} consistency={active_state.get('consistency_status')}",
                )
            )

    candidate = None
    if not findings:
        target_version = derive_candidate_version(active_state["active_baseline_version"])
        if target_version is None:
            findings.append(
                _finding(
                    "candidate_version_invalid",
                    "deny",
                    "active_baseline_version",
                    "could not derive a strictly forward target version",
                )
            )
        else:
            candidate = build_promotion_candidate(
                convergence_report=report,
                convergence_report_path=convergence_path,
                active_state=active_state,
                reason=args.reason,
                approval_scope=args.approval_scope,
            )
            existing = _latest_candidate_states(_load_candidate_registry(registry_path)).values()
            for record in existing:
                if (
                    record.get("status") == "pending"
                    and record.get("source_convergence_evidence_hash") == candidate["source_convergence_evidence_hash"]
                    and record.get("source_active_baseline_version") == candidate["source_active_baseline_version"]
                    and record.get("target_baseline_version") == candidate["target_baseline_version"]
                    and record.get("approval_scope") == candidate["approval_scope"]
                ):
                    findings.append(
                        _finding(
                            "candidate_already_exists",
                            "deny",
                            str(registry_path),
                            "a pending candidate for the same bound state already exists",
                        )
                    )
                    break

    decision = "FAIL" if any(item["severity"] == "deny" for item in findings) else "PASS"
    if decision == "PASS" and args.generate:
        try:
            write_candidate_record(registry_path, candidate)
        except Exception as exc:
            findings.append(
                _finding(
                    "candidate_registry_write_failed",
                    "deny",
                    str(registry_path),
                    f"failed to append candidate record: {exc}",
                )
            )
            findings.append(
                _finding(
                    "candidate_generation_fail_closed",
                    "deny",
                    str(repo_root),
                    "candidate generation failed closed after registry write failure",
                )
            )
            decision = "FAIL"
    elif decision == "PASS" and args.verify_only:
        decision = "WARN"
    elif decision == "FAIL":
        findings.append(
            _finding(
                "candidate_generation_fail_closed",
                "deny",
                str(repo_root),
                "candidate generation failed closed due to blocking inconsistencies",
            )
        )

    report_payload = {
        "audit_type": "sot_promotion_candidate_generator",
        "timestamp_utc": _utc_now_iso(),
        "repo_root": str(repo_root),
        "mode": mode,
        "decision": decision,
        "candidate": candidate,
        "findings": findings,
        "finding_codes": [item["finding_code"] for item in findings],
        "evidence_hash": "",
    }
    report_payload["evidence_hash"] = _json_sha256({k: v for k, v in report_payload.items() if k != "evidence_hash"})
    emit_candidate_report(report_payload, output_dir)

    if args.json:
        print(json.dumps(report_payload, indent=2, ensure_ascii=False))
    elif args.markdown:
        print((output_dir / REPORT_MD).read_text(encoding="utf-8"))
    else:
        print(f"SoT Promotion Candidate Generator: {decision}")
        print(f"  Findings: {len(findings)}")
        print(f"  Report: {output_dir / REPORT_JSON}")
    return EXIT_FAIL if decision == "FAIL" else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
