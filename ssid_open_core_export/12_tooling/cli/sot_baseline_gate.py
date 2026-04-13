#!/usr/bin/env python3
"""Canonical SoT Baseline + Change Intent Gate — CC-SSID-SOT-BASELINE-01.

Provides a frozen baseline snapshot of the 9 canonical SoT artifacts and
enforces a change intent requirement when artifacts are modified.

Modes:
  --create-baseline   Build and save a new baseline snapshot
  --check             Full gate evaluation (baseline + intent validation)
  --verify-only       Only verify baseline exists and is valid

Exit codes:
  0 = PASS or WARN
  2 = FAIL
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cross_artifact_reference_audit import (
    SOT_ARTIFACTS,
    AuditResult,
    Finding,
    extract_contract_rules,
    extract_rego_rule_ids,
    extract_validator_rules,
    sha256_file,
)

EXIT_PASS = 0
EXIT_FAIL = 2

BASELINE_VERSION = "1.0.0"

DEFAULT_BASELINE_REL = "24_meta_orchestration/registry/sot_baseline_snapshot.json"
DEFAULT_INTENT_REL = "02_audit_logging/reports/sot_change_intent.json"
DEFAULT_OUTPUT_REL = "02_audit_logging/reports/"

RULE_ID_PATTERN = re.compile(r"SOT_AGENT_\d{3}")


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(obj: Any) -> str:
    """SHA-256 of JSON-serialized object."""
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _extract_version(artifact_id: str, path: Path) -> str | None:
    """Try to extract a version string from an artifact file."""
    try:
        if artifact_id == "contract":
            _, version = extract_contract_rules(path)
            return version
        if artifact_id == "validator_core":
            _, _, version = extract_validator_rules(path)
            return version
        if artifact_id == "rego":
            _, version = extract_rego_rule_ids(path)
            return version
        if artifact_id == "validator_cli":
            text = path.read_text(encoding="utf-8")
            m = re.search(r'(?:VERSION|__version__)\s*=\s*["\']([^"\']+)["\']', text)
            if m:
                return m.group(1)
            m = re.search(r"#.*\bv(\d+\.\d+(?:\.\d+)?)\b", text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _extract_rule_count(artifact_id: str, path: Path) -> int | None:
    """Try to extract the rule count from an artifact file."""
    try:
        if artifact_id == "contract":
            rules, _ = extract_contract_rules(path)
            return len(rules)
        if artifact_id == "validator_core":
            rules_keys, _, _ = extract_validator_rules(path)
            return len(rules_keys)
        if artifact_id == "rego":
            rules, _ = extract_rego_rule_ids(path)
            return len(rules)
        # For other text-based artifacts, count SOT_AGENT_NNN pattern matches
        text = path.read_text(encoding="utf-8")
        ids = set(RULE_ID_PATTERN.findall(text))
        if ids:
            return len(ids)
    except Exception:
        pass
    return None


def _detect_repo_root() -> Path:
    """Auto-detect repo root from script location (two levels up)."""
    return Path(__file__).resolve().parents[2]


# -----------------------------------------------------------------------
# build_baseline_snapshot
# -----------------------------------------------------------------------
def build_baseline_snapshot(repo: Path) -> dict:
    """Create a deterministic snapshot of all 9 SoT artifacts."""
    ts = _utc_now_iso()
    snapshot_id = f"BL-{ts}"

    artifacts_list: list[dict] = []
    for artifact_id, rel_path in SOT_ARTIFACTS.items():
        full_path = repo / rel_path
        entry: dict[str, Any] = {
            "artifact_id": artifact_id,
            "path": rel_path,
            "sha256": sha256_file(full_path) if full_path.exists() else None,
            "version": _extract_version(artifact_id, full_path) if full_path.exists() else None,
            "rule_count": _extract_rule_count(artifact_id, full_path) if full_path.exists() else None,
        }
        artifacts_list.append(entry)

    evidence_hash = _json_sha256(artifacts_list)

    return {
        "snapshot_id": snapshot_id,
        "created_at_utc": ts,
        "baseline_version": BASELINE_VERSION,
        "scope": "canonical_sot",
        "artifact_count": len(SOT_ARTIFACTS),
        "artifacts": artifacts_list,
        "evidence_hash": evidence_hash,
        "generator": "sot_baseline_gate.py",
    }


# -----------------------------------------------------------------------
# load_baseline_snapshot
# -----------------------------------------------------------------------
def load_baseline_snapshot(path: Path) -> dict | None:
    """Load and validate a baseline JSON file. Returns None if invalid."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    required = {"snapshot_id", "created_at_utc", "artifacts", "evidence_hash"}
    if not isinstance(data, dict):
        return None
    if not required.issubset(data.keys()):
        return None
    if not isinstance(data["artifacts"], list):
        return None

    return data


# -----------------------------------------------------------------------
# load_change_intent
# -----------------------------------------------------------------------
def load_change_intent(path: Path) -> dict | None:
    """Load a change intent JSON file. Returns None if invalid."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    required = {"intent_id", "change_type", "affected_artifacts"}
    if not isinstance(data, dict):
        return None
    if not required.issubset(data.keys()):
        return None
    if not isinstance(data["affected_artifacts"], list):
        return None

    return data


# -----------------------------------------------------------------------
# compare_workspace_to_baseline
# -----------------------------------------------------------------------
def compare_workspace_to_baseline(
    repo: Path,
    baseline: dict,
) -> tuple[AuditResult, list[dict]]:
    """Compare current workspace against the baseline snapshot.

    Returns (AuditResult with findings, list of changed artifact dicts).
    """
    result = AuditResult()
    changed_artifacts: list[dict] = []

    # Validate baseline artifact scope
    baseline_ids = {a["artifact_id"] for a in baseline["artifacts"] if "artifact_id" in a}
    expected_ids = set(SOT_ARTIFACTS.keys())

    if baseline_ids != expected_ids:
        missing = expected_ids - baseline_ids
        extra = baseline_ids - expected_ids
        detail_parts = []
        if missing:
            detail_parts.append(f"missing={sorted(missing)}")
        if extra:
            detail_parts.append(f"extra={sorted(extra)}")
        result.add(
            Finding(
                "artifact_scope_mismatch",
                "deny",
                "baseline",
                f"baseline artifact scope differs from expected: {', '.join(detail_parts)}",
            )
        )

    for bl_artifact in baseline["artifacts"]:
        artifact_id = bl_artifact.get("artifact_id", "?")
        rel_path = bl_artifact.get("path", "")
        bl_hash = bl_artifact.get("sha256")
        bl_rule_count = bl_artifact.get("rule_count")

        full_path = repo / rel_path
        if not full_path.exists():
            # File missing — treat as changed (hash mismatch)
            if bl_hash is not None:
                changed_artifacts.append(
                    {
                        "artifact_id": artifact_id,
                        "path": rel_path,
                        "baseline_sha256": bl_hash,
                        "current_sha256": None,
                        "baseline_rule_count": bl_rule_count,
                        "current_rule_count": None,
                    }
                )
                result.add(
                    Finding(
                        "baseline_hash_mismatch",
                        "deny",
                        rel_path,
                        f"artifact '{artifact_id}' missing on disk (was in baseline)",
                    )
                )
            continue

        current_hash = sha256_file(full_path)
        current_rule_count = _extract_rule_count(artifact_id, full_path)

        if bl_hash is not None and current_hash != bl_hash:
            changed_artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "path": rel_path,
                    "baseline_sha256": bl_hash,
                    "current_sha256": current_hash,
                    "baseline_rule_count": bl_rule_count,
                    "current_rule_count": current_rule_count,
                }
            )
            result.add(
                Finding(
                    "baseline_hash_mismatch",
                    "deny",
                    rel_path,
                    f"artifact '{artifact_id}' hash differs from baseline: "
                    f"baseline={bl_hash[:16]}..., current={current_hash[:16]}...",
                )
            )

            # Check rule count drift
            if bl_rule_count is not None and current_rule_count is not None and bl_rule_count != current_rule_count:
                result.add(
                    Finding(
                        "baseline_rule_count_drift",
                        "deny",
                        rel_path,
                        f"artifact '{artifact_id}' rule count changed: "
                        f"baseline={bl_rule_count}, current={current_rule_count}",
                    )
                )

    return result, changed_artifacts


# -----------------------------------------------------------------------
# evaluate_baseline_gate
# -----------------------------------------------------------------------
def evaluate_baseline_gate(
    repo: Path,
    baseline: dict | None,
    intent: dict | None,
    changed_artifacts: list[dict],
    result: AuditResult,
) -> str:
    """Main evaluation logic. Returns 'PASS', 'WARN', or 'FAIL'."""

    # Rule 1: No baseline
    if baseline is None:
        result.add(
            Finding(
                "baseline_missing",
                "deny",
                DEFAULT_BASELINE_REL,
                "no baseline snapshot found — cannot evaluate drift",
            )
        )
        return "FAIL"

    # Rule 2: Invalid baseline schema (already validated in load, but double-check)
    required = {"snapshot_id", "created_at_utc", "artifacts", "evidence_hash"}
    if not required.issubset(baseline.keys()) or not isinstance(baseline["artifacts"], list):
        result.add(
            Finding(
                "baseline_schema_invalid",
                "deny",
                DEFAULT_BASELINE_REL,
                "baseline snapshot has invalid schema",
            )
        )
        return "FAIL"

    # Rule 8: No changes detected
    if not changed_artifacts:
        return "PASS"

    changed_ids = {a["artifact_id"] for a in changed_artifacts}

    # Rule 3: Changes detected but no intent
    if intent is None:
        for cid in sorted(changed_ids):
            result.add(
                Finding(
                    "intent_missing_for_canonical_change",
                    "deny",
                    DEFAULT_INTENT_REL,
                    f"artifact '{cid}' changed but no change intent file provided",
                )
            )
        return "FAIL"

    # Rule 7: Metadata/report/registry refresh intents → WARN
    if intent.get("change_type") in ("metadata_only", "report_refresh", "registry_refresh"):
        # Still check but return WARN
        return "WARN"

    # Rule 4: Intent affected_artifacts don't match actual changes
    declared_ids = set(intent.get("affected_artifacts", []))

    undeclared = changed_ids - declared_ids
    if undeclared:
        for uid in sorted(undeclared):
            result.add(
                Finding(
                    "undeclared_baseline_drift",
                    "deny",
                    DEFAULT_INTENT_REL,
                    f"artifact '{uid}' changed but not declared in intent affected_artifacts",
                )
            )

    not_actually_changed = declared_ids - changed_ids
    if not_actually_changed:
        for nid in sorted(not_actually_changed):
            result.add(
                Finding(
                    "declared_change_not_fully_propagated",
                    "deny",
                    DEFAULT_INTENT_REL,
                    f"artifact '{nid}' declared in intent but not actually changed in workspace",
                )
            )

    if undeclared or not_actually_changed:
        return "FAIL"

    # Rule 5: Rule count delta mismatch
    expected_delta = intent.get("expected_rule_count_delta")
    if expected_delta is not None:
        for ca in changed_artifacts:
            bl_rc = ca.get("baseline_rule_count")
            cur_rc = ca.get("current_rule_count")
            if bl_rc is not None and cur_rc is not None:
                actual_delta = cur_rc - bl_rc
                if actual_delta != expected_delta:
                    result.add(
                        Finding(
                            "unexpected_rule_count_delta",
                            "deny",
                            ca.get("path", "?"),
                            f"artifact '{ca['artifact_id']}' rule count delta: "
                            f"expected={expected_delta}, actual={actual_delta}",
                        )
                    )
                    return "FAIL"

    # Rule 6: Everything changed and declared, but baseline not refreshed
    # If the baseline's evidence_hash no longer matches the current artifacts state,
    # and changes are declared and propagated, the baseline itself is stale.
    current_snapshot = build_baseline_snapshot(repo)
    if current_snapshot["evidence_hash"] != baseline.get("evidence_hash"):
        result.add(
            Finding(
                "stale_baseline_after_declared_change",
                "deny",
                DEFAULT_BASELINE_REL,
                "changes are declared and propagated but baseline snapshot is stale — run --create-baseline to refresh",
            )
        )
        return "FAIL"

    # Rule 9: Fully declared + fully propagated
    return "PASS"


# -----------------------------------------------------------------------
# emit_reports
# -----------------------------------------------------------------------
def emit_reports(report: dict, output_dir: Path) -> None:
    """Write JSON and Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    json_path = output_dir / "sot_baseline_gate_report.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Markdown report
    md_path = output_dir / "sot_baseline_gate_report.md"
    md_lines: list[str] = []

    decision = report.get("decision", "UNKNOWN")
    md_lines.append("# SoT Baseline Gate Report")
    md_lines.append("")

    # Summary
    md_lines.append("## Summary")
    md_lines.append("")
    md_lines.append("| Field | Value |")
    md_lines.append("|-------|-------|")
    md_lines.append(f"| Decision | **{decision}** |")
    md_lines.append(f"| Timestamp | {report.get('timestamp_utc', 'N/A')} |")
    md_lines.append(f"| Repo | `{report.get('repo', 'N/A')}` |")
    md_lines.append(f"| Findings | {report.get('finding_count', 0)} |")
    md_lines.append(f"| Deny | {report.get('deny_count', 0)} |")
    md_lines.append(f"| Warn | {report.get('warn_count', 0)} |")
    md_lines.append(f"| Evidence Hash | `{report.get('evidence_hash', 'N/A')[:16]}...` |")
    md_lines.append("")

    # Changed Artifacts
    md_lines.append("## Changed Artifacts")
    md_lines.append("")
    changed = report.get("changed_artifacts", [])
    if changed:
        md_lines.append("| Artifact | Path | Baseline Hash | Current Hash |")
        md_lines.append("|----------|------|---------------|--------------|")
        for ca in changed:
            bl_h = ca.get("baseline_sha256", "N/A") or "N/A"
            cur_h = ca.get("current_sha256", "N/A") or "N/A"
            md_lines.append(
                f"| {ca.get('artifact_id', '?')} | `{ca.get('path', '?')}` | `{bl_h[:16]}...` | `{cur_h[:16]}...` |"
            )
    else:
        md_lines.append("No artifacts changed relative to baseline.")
    md_lines.append("")

    # Intent Validation
    md_lines.append("## Intent Validation")
    md_lines.append("")
    intent_meta = report.get("intent_metadata")
    if intent_meta:
        md_lines.append(f"- Intent ID: `{intent_meta.get('intent_id', 'N/A')}`")
        md_lines.append(f"- Change Type: `{intent_meta.get('change_type', 'N/A')}`")
        md_lines.append(f"- Affected Artifacts: {intent_meta.get('affected_artifacts', [])}")
    else:
        md_lines.append("No change intent file provided.")
    md_lines.append("")

    # Baseline Comparison
    md_lines.append("## Baseline Comparison")
    md_lines.append("")
    bl_meta = report.get("baseline_metadata")
    if bl_meta:
        md_lines.append(f"- Snapshot ID: `{bl_meta.get('snapshot_id', 'N/A')}`")
        md_lines.append(f"- Created: {bl_meta.get('created_at_utc', 'N/A')}")
        md_lines.append(f"- Artifact Count: {bl_meta.get('artifact_count', 'N/A')}")
    else:
        md_lines.append("No baseline loaded.")
    md_lines.append("")

    # Findings Table
    md_lines.append("## Findings")
    md_lines.append("")
    findings = report.get("findings", [])
    if findings:
        md_lines.append("| # | Severity | Class | Path | Detail |")
        md_lines.append("|---|----------|-------|------|--------|")
        for i, f in enumerate(findings, 1):
            sev = f.get("severity", "?").upper()
            md_lines.append(
                f"| {i} | {sev} | `{f.get('class', '?')}` | `{f.get('path', '?')}` | {f.get('detail', '')} |"
            )
    else:
        md_lines.append("No findings.")
    md_lines.append("")

    # Final Decision
    md_lines.append("## Final Decision")
    md_lines.append("")
    md_lines.append(f"**{decision}**")
    md_lines.append("")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")


# -----------------------------------------------------------------------
# build_report_dict
# -----------------------------------------------------------------------
def build_report_dict(
    repo: Path,
    decision: str,
    baseline: dict | None,
    intent: dict | None,
    changed_artifacts: list[dict],
    result: AuditResult,
) -> dict:
    """Assemble the final report dictionary."""
    ts = _utc_now_iso()

    baseline_meta: dict | None = None
    if baseline is not None:
        baseline_meta = {
            "snapshot_id": baseline.get("snapshot_id"),
            "created_at_utc": baseline.get("created_at_utc"),
            "baseline_version": baseline.get("baseline_version"),
            "artifact_count": baseline.get("artifact_count"),
            "evidence_hash": baseline.get("evidence_hash"),
        }

    intent_meta: dict | None = None
    if intent is not None:
        intent_meta = {
            "intent_id": intent.get("intent_id"),
            "change_type": intent.get("change_type"),
            "affected_artifacts": intent.get("affected_artifacts"),
        }

    expected_artifacts = sorted(SOT_ARTIFACTS.keys())
    actual_artifacts = sorted({a.get("artifact_id", "?") for a in (baseline.get("artifacts", []) if baseline else [])})

    findings_dicts = [f.to_dict() for f in result.findings]
    evidence_hash = _json_sha256(findings_dicts)

    return {
        "audit_type": "sot_baseline_gate",
        "timestamp_utc": ts,
        "repo": str(repo),
        "decision": decision,
        "baseline_metadata": baseline_meta,
        "intent_metadata": intent_meta,
        "changed_artifacts": changed_artifacts,
        "expected_artifacts": expected_artifacts,
        "actual_artifacts": actual_artifacts,
        "finding_count": len(result.findings),
        "deny_count": sum(1 for f in result.findings if f.severity == "deny"),
        "warn_count": sum(1 for f in result.findings if f.severity == "warn"),
        "evidence_hash": evidence_hash,
        "findings": findings_dicts,
    }


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sot_baseline_gate.py",
        description="Canonical SoT Baseline + Change Intent Gate.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--create-baseline",
        action="store_true",
        help="build and save a new baseline snapshot",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="full gate evaluation (baseline comparison + intent validation)",
    )
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="only verify baseline exists and is valid",
    )

    parser.add_argument(
        "--repo-root",
        default=None,
        help="SSID repo root (default: auto-detect)",
    )
    parser.add_argument(
        "--baseline-file",
        default=None,
        help=f"path to baseline snapshot JSON (default: <repo>/{DEFAULT_BASELINE_REL})",
    )
    parser.add_argument(
        "--intent-file",
        default=None,
        help=f"path to change intent JSON (default: <repo>/{DEFAULT_INTENT_REL})",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"report output directory (default: <repo>/{DEFAULT_OUTPUT_REL})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON output to stdout",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Markdown output to stdout",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo = Path(args.repo_root).resolve() if args.repo_root else _detect_repo_root()
    baseline_path = Path(args.baseline_file) if args.baseline_file else repo / DEFAULT_BASELINE_REL
    intent_path = Path(args.intent_file) if args.intent_file else repo / DEFAULT_INTENT_REL
    output_dir = Path(args.output_dir) if args.output_dir else repo / DEFAULT_OUTPUT_REL

    # --create-baseline
    if args.create_baseline:
        snapshot = build_baseline_snapshot(repo)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if args.json:
            print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        else:
            print(f"Baseline snapshot created: {baseline_path}")
            print(f"  Snapshot ID:    {snapshot['snapshot_id']}")
            print(f"  Artifacts:      {snapshot['artifact_count']}")
            print(f"  Evidence Hash:  {snapshot['evidence_hash'][:16]}...")
        return EXIT_PASS

    # --verify-only
    if args.verify_only:
        baseline = load_baseline_snapshot(baseline_path)
        if baseline is None:
            if args.json:
                print(json.dumps({"valid": False, "path": str(baseline_path)}, indent=2))
            else:
                print(f"FAIL: baseline not found or invalid at {baseline_path}")
            return EXIT_FAIL

        if args.json:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "path": str(baseline_path),
                        "snapshot_id": baseline.get("snapshot_id"),
                        "artifact_count": baseline.get("artifact_count"),
                        "created_at_utc": baseline.get("created_at_utc"),
                        "evidence_hash": baseline.get("evidence_hash"),
                    },
                    indent=2,
                )
            )
        else:
            print(f"PASS: baseline is valid at {baseline_path}")
            print(f"  Snapshot ID:    {baseline.get('snapshot_id')}")
            print(f"  Artifacts:      {baseline.get('artifact_count')}")
            print(f"  Created:        {baseline.get('created_at_utc')}")
        return EXIT_PASS

    # --check (full gate evaluation)
    result = AuditResult()

    baseline = load_baseline_snapshot(baseline_path)
    intent = load_change_intent(intent_path)

    changed_artifacts: list[dict] = []
    if baseline is not None:
        comparison_result, changed_artifacts = compare_workspace_to_baseline(repo, baseline)
        # Merge comparison findings into main result
        for f in comparison_result.findings:
            result.add(f)

    decision = evaluate_baseline_gate(repo, baseline, intent, changed_artifacts, result)

    report = build_report_dict(repo, decision, baseline, intent, changed_artifacts, result)

    # Emit reports to files
    emit_reports(report, output_dir)

    # Console output
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        md_path = output_dir / "sot_baseline_gate_report.md"
        if md_path.exists():
            print(md_path.read_text(encoding="utf-8"))
    else:
        print(f"SoT Baseline Gate: {decision}")
        print(f"  Findings: {report['finding_count']} (deny={report['deny_count']}, warn={report['warn_count']})")
        print(f"  Changed:  {len(changed_artifacts)} artifact(s)")
        print(f"  Evidence: {report['evidence_hash'][:16]}...")
        if result.findings:
            print()
            for f in result.findings:
                tag = "FAIL" if f.severity == "deny" else f.severity.upper()
                print(f"  [{tag}] {f.finding_class}: {f.path}")
                print(f"         {f.detail}")
        print(f"\n  Reports written to: {output_dir}")

    if decision == "FAIL":
        return EXIT_FAIL
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
