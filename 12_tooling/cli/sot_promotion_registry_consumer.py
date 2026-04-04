#!/usr/bin/env python3
"""Consume promotion records into an active baseline registry state."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 2

DEFAULT_OUTPUT_REL = "02_audit_logging/reports"
DEFAULT_BASELINE_REL = "24_meta_orchestration/registry/sot_baseline_snapshot.json"
DEFAULT_PROMOTIONS_REL = "24_meta_orchestration/registry/sot_baseline_promotions.jsonl"
DEFAULT_ACTIVE_STATE_REL = "24_meta_orchestration/registry/sot_active_baseline_state.json"
REPORT_JSON = "sot_promotion_registry_consumption_report.json"
REPORT_MD = "sot_promotion_registry_consumption_report.md"

PROMOTION_REQUIRED_FIELDS = (
    "promotion_id",
    "approved_at_utc",
    "approval_id",
    "source_convergence_report",
    "source_convergence_evidence_hash",
    "previous_baseline_version",
    "promoted_baseline_version",
    "decision",
    "baseline_sha256",
    "promotion_evidence_hash",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _snapshot_sha(snapshot: dict) -> str:
    embedded = snapshot.get("baseline_sha256") if isinstance(snapshot, dict) else None
    if isinstance(embedded, str) and embedded:
        return embedded
    return _json_sha256(snapshot)


def _parse_version(version: str) -> tuple[int, int, int] | None:
    parts = str(version).split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _finding(code: str, severity: str, path: str, detail: str) -> dict[str, str]:
    return {"finding_code": code, "severity": severity, "path": path, "detail": detail}


def load_baseline_snapshot(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    required = {"baseline_version", "scope", "created_at_utc"}
    return data if isinstance(data, dict) and required.issubset(data.keys()) else None


def load_promotion_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append({"_invalid_jsonl_line": line})
    return records


def resolve_active_promotion(records: list[dict]) -> tuple[dict | None, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    valid_records: list[dict] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict) or "_invalid_jsonl_line" in record:
            findings.append(
                _finding(
                    "promotion_record_invalid",
                    "deny",
                    f"promotions[{index}]",
                    "promotion record is not valid JSON object",
                )
            )
            continue
        missing = [field for field in PROMOTION_REQUIRED_FIELDS if field not in record]
        if missing:
            findings.append(
                _finding(
                    "promotion_record_invalid",
                    "deny",
                    f"promotions[{index}]",
                    f"promotion record missing required fields: {missing}",
                )
            )
            continue
        if record.get("decision") != "approve":
            findings.append(
                _finding(
                    "promotion_record_invalid",
                    "deny",
                    f"promotions[{index}].decision",
                    f"promotion record decision must be approve, got '{record.get('decision')}'",
                )
            )
            continue
        if _parse_version(record.get("promoted_baseline_version")) is None:
            findings.append(
                _finding(
                    "promotion_record_invalid",
                    "deny",
                    f"promotions[{index}].promoted_baseline_version",
                    "promoted_baseline_version is not strict semver",
                )
            )
            continue
        valid_records.append(record)
    if not valid_records:
        findings.append(
            _finding(
                "active_promotion_unresolved",
                "deny",
                "promotions",
                "no valid promotion record could be resolved as active",
            )
        )
        return None, findings
    valid_records.sort(key=lambda item: item["approved_at_utc"])
    return valid_records[-1], findings


def build_active_baseline_state(snapshot: dict, promotion_record: dict, snapshot_path: Path) -> dict[str, Any]:
    snapshot_sha = _snapshot_sha(snapshot)
    state = {
        "state_id": f"ABS-{_utc_now_iso()}",
        "updated_at_utc": _utc_now_iso(),
        "active_baseline_version": snapshot["baseline_version"],
        "baseline_snapshot_path": str(snapshot_path),
        "baseline_snapshot_sha256": snapshot_sha,
        "source_promotion_id": promotion_record["promotion_id"],
        "source_approval_id": promotion_record["approval_id"],
        "source_convergence_report": promotion_record["source_convergence_report"],
        "source_convergence_evidence_hash": promotion_record["source_convergence_evidence_hash"],
        "decision": promotion_record["decision"],
        "scope": snapshot.get("scope", "canonical_sot"),
        "consistency_status": "CONSISTENT",
        "evidence_hash": "",
    }
    state["evidence_hash"] = _json_sha256({k: v for k, v in state.items() if k != "evidence_hash"})
    return state


def validate_registry_consistency(
    snapshot: dict | None, promotion_record: dict | None, active_state: dict | None
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if snapshot is None:
        return [
            _finding(
                "baseline_snapshot_missing", "deny", DEFAULT_BASELINE_REL, "baseline snapshot missing or unreadable"
            )
        ]
    if promotion_record is None:
        return [
            _finding(
                "active_promotion_unresolved",
                "deny",
                DEFAULT_PROMOTIONS_REL,
                "no active promotion record available for consistency validation",
            )
        ]
    if active_state is None:
        return [
            _finding(
                "registry_consistency_failed", "deny", DEFAULT_ACTIVE_STATE_REL, "active baseline state was not built"
            )
        ]
    snapshot_sha = _snapshot_sha(snapshot)
    if promotion_record.get("baseline_sha256") != snapshot_sha:
        findings.append(
            _finding(
                "baseline_snapshot_hash_mismatch",
                "deny",
                DEFAULT_BASELINE_REL,
                "promotion record baseline_sha256 does not match current baseline snapshot",
            )
        )
    if active_state.get("baseline_snapshot_sha256") != snapshot_sha:
        findings.append(
            _finding(
                "registry_consistency_failed",
                "deny",
                DEFAULT_ACTIVE_STATE_REL,
                "active baseline state snapshot hash does not match current baseline snapshot",
            )
        )
    if active_state.get("active_baseline_version") != snapshot.get("baseline_version"):
        findings.append(
            _finding(
                "registry_consistency_failed",
                "deny",
                DEFAULT_ACTIVE_STATE_REL,
                "active baseline version does not match baseline snapshot version",
            )
        )
    if active_state.get("active_baseline_version") != promotion_record.get("promoted_baseline_version"):
        findings.append(
            _finding(
                "registry_consistency_failed",
                "deny",
                DEFAULT_ACTIVE_STATE_REL,
                "active baseline version does not match promotion record version",
            )
        )
    if active_state.get("decision") != "approve":
        findings.append(
            _finding(
                "registry_consistency_failed", "deny", DEFAULT_ACTIVE_STATE_REL, "active state decision is not approve"
            )
        )
    if active_state.get("scope") not in {"canonical_sot", "full_canonical_sot"}:
        findings.append(
            _finding("registry_consistency_failed", "deny", DEFAULT_ACTIVE_STATE_REL, "active state scope is invalid")
        )
    return findings


def emit_registry_consumption_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON
    md_path = output_dir / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# SoT Promotion Registry Consumption Report",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Decision | **{report['decision']}** |",
        f"| Mode | `{report['mode']}` |",
        f"| Updated | {report['timestamp_utc']} |",
        f"| Active State Path | `{report['active_state_path']}` |",
        f"| Evidence Hash | `{report['evidence_hash']}` |",
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
    lines.extend(
        [
            "",
            "## Active Baseline",
            "",
            f"- Baseline version: `{report['active_baseline_state'].get('active_baseline_version') if report['active_baseline_state'] else None}`",
            f"- Source promotion: `{report['active_baseline_state'].get('source_promotion_id') if report['active_baseline_state'] else None}`",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sot_promotion_registry_consumer.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--refresh-active-state", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    baseline_path = repo_root / DEFAULT_BASELINE_REL
    promotions_path = repo_root / DEFAULT_PROMOTIONS_REL
    active_state_path = repo_root / DEFAULT_ACTIVE_STATE_REL
    mode = "refresh-active-state" if args.refresh_active_state else "verify-only" if args.verify_only else "check"

    findings: list[dict[str, str]] = []
    snapshot = load_baseline_snapshot(baseline_path)
    if snapshot is None:
        findings.append(
            _finding(
                "baseline_snapshot_missing", "deny", str(baseline_path), "baseline snapshot is missing or unreadable"
            )
        )
    records = load_promotion_records(promotions_path)
    if not promotions_path.exists() or not records:
        findings.append(
            _finding(
                "promotion_records_missing",
                "deny",
                str(promotions_path),
                "promotion records registry is missing or empty",
            )
        )
        active_record = None
    else:
        active_record, record_findings = resolve_active_promotion(records)
        findings.extend(record_findings)

    active_state = (
        build_active_baseline_state(snapshot, active_record, baseline_path) if snapshot and active_record else None
    )
    findings.extend(validate_registry_consistency(snapshot, active_record, active_state))

    decision = "FAIL" if any(item["severity"] == "deny" for item in findings) else "PASS"
    if decision == "PASS" and args.verify_only:
        decision = "WARN"

    if args.refresh_active_state and decision == "PASS":
        try:
            active_state_path.write_text(
                json.dumps(active_state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        except Exception as exc:
            findings.append(
                _finding(
                    "active_state_write_failed",
                    "deny",
                    str(active_state_path),
                    f"failed to write active baseline state: {exc}",
                )
            )
            findings.append(
                _finding(
                    "registry_consumption_fail_closed",
                    "deny",
                    str(repo_root),
                    "registry consumer failed closed after active state write failure",
                )
            )
            decision = "FAIL"
    elif decision == "FAIL":
        findings.append(
            _finding(
                "registry_consumption_fail_closed",
                "deny",
                str(repo_root),
                "registry consumer failed closed due to blocking inconsistencies",
            )
        )

    report = {
        "audit_type": "sot_promotion_registry_consumer",
        "timestamp_utc": _utc_now_iso(),
        "mode": mode,
        "repo_root": str(repo_root),
        "baseline_snapshot_path": str(baseline_path),
        "promotion_records_path": str(promotions_path),
        "active_state_path": str(active_state_path),
        "decision": decision,
        "findings": findings,
        "finding_codes": [item["finding_code"] for item in findings],
        "active_baseline_state": active_state,
        "evidence_hash": "",
    }
    report["evidence_hash"] = _json_sha256({k: v for k, v in report.items() if k != "evidence_hash"})
    emit_registry_consumption_report(report, output_dir)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        print((output_dir / REPORT_MD).read_text(encoding="utf-8"))
    else:
        print(f"SoT Promotion Registry Consumer: {decision}")
        print(f"  Findings: {len(findings)}")
        print(f"  Report: {output_dir / REPORT_JSON}")

    return EXIT_FAIL if decision == "FAIL" else EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
