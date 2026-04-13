#!/usr/bin/env python3
"""
Gate Remediation Planner — classifies gate findings and generates fix plans.

Reads findings JSON from the 3 gates (registry enforcement, export scope,
integrity) and produces a structured remediation plan with per-finding
patch proposals.

Remediation classes:
- auto_fix_safe:          Low-risk normalizations, auto-applicable
- manual_review_required: Needs human review before fix
- hard_block_no_fix:      No automated fix available

Produces: remediation_plan.json, remediation_report.md
Exit codes: 0=all auto-fixable, 1=some manual review, 2=hard blocks present, 3=error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_ALL_AUTO = 0
EXIT_MANUAL = 1
EXIT_HARD_BLOCK = 2
EXIT_ERROR = 3

# ---------------------------------------------------------------------------
# Finding class -> Remediation class mapping
# ---------------------------------------------------------------------------
FINDING_TO_REMEDIATION: Dict[str, str] = {
    # auto_fix_safe — low risk, reversible, no approval needed
    "format_inconsistency": "auto_fix_safe",
    "sha256_prefix_normalization": "auto_fix_safe",
    "evidence_ref_string_to_object": "auto_fix_safe",
    "missing_evidence_ref": "auto_fix_safe",  # only when file exists + hash derivable
    "sort_format_inconsistency": "auto_fix_safe",

    # manual_review_required — needs human approval
    "hash_mismatch": "manual_review_required",
    "duplicate_artifact_id": "manual_review_required",
    "duplicate_path": "manual_review_required",
    "missing_required_export_artifact": "manual_review_required",
    "canonical_derivative_hash_drift": "manual_review_required",
    "unsanitized_artifact": "manual_review_required",
    "missing_source_of_truth_ref": "manual_review_required",
    "orphan_registry_entry": "manual_review_required",
    "unregistered_artifact": "manual_review_required",
    "invalid_evidence_ref": "manual_review_required",

    # hard_block_no_fix — no automated fix, critical risk
    "forbidden_public_artifact": "hard_block_no_fix",
    "fail_open_guard": "hard_block_no_fix",
    "registry_schema_invalid": "hard_block_no_fix",
    "export_scope_violation": "hard_block_no_fix",
}

# ---------------------------------------------------------------------------
# Remediation class -> default patch proposal attributes
# ---------------------------------------------------------------------------
_REMEDIATION_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "auto_fix_safe": {
        "risk_level": "low",
        "requires_approval": False,
        "reversible": True,
    },
    "manual_review_required": {
        "risk_level": "medium",
        "requires_approval": True,
        "reversible": True,
    },
    "hard_block_no_fix": {
        "risk_level": "critical",
        "requires_approval": True,
        "reversible": False,
    },
}

# ---------------------------------------------------------------------------
# Operation templates per finding class
# ---------------------------------------------------------------------------
_OPERATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "format_inconsistency": {
        "operation": "normalize",
        "precondition": "registry entry exists",
        "proposed_change": "Normalize field formatting to canonical form",
    },
    "sha256_prefix_normalization": {
        "operation": "normalize",
        "precondition": "hash_sha256 field contains sha256: prefix",
        "proposed_change": "Strip sha256: prefix from hash_sha256 field",
    },
    "evidence_ref_string_to_object": {
        "operation": "normalize",
        "precondition": "evidence_ref is a plain string",
        "proposed_change": "Convert evidence_ref string to canonical object {type, hash, path}",
    },
    "missing_evidence_ref": {
        "operation": "register",
        "precondition": "file exists and hash computable",
        "proposed_change": "Add evidence_ref with computed hash and path from disk artifact",
    },
    "sort_format_inconsistency": {
        "operation": "normalize",
        "precondition": "registry is parseable",
        "proposed_change": "Re-sort registry entries and normalize JSON formatting",
    },
    "hash_mismatch": {
        "operation": "update",
        "precondition": "file exists on disk, registry hash differs",
        "proposed_change": "Requires manual verification: disk hash differs from registry hash",
    },
    "duplicate_artifact_id": {
        "operation": "delete",
        "precondition": "duplicate artifact name exists in registry",
        "proposed_change": "Remove duplicate registry entry after manual review of which to keep",
    },
    "duplicate_path": {
        "operation": "delete",
        "precondition": "duplicate path exists in registry",
        "proposed_change": "Remove duplicate path entry after manual review of which to keep",
    },
    "missing_required_export_artifact": {
        "operation": "create",
        "precondition": "export manifest requires artifact not present in registry",
        "proposed_change": "Register missing export artifact after manual verification",
    },
    "canonical_derivative_hash_drift": {
        "operation": "update",
        "precondition": "canonical and derivative hashes diverged",
        "proposed_change": "Rebuild derivative from canonical source after manual review",
    },
    "unsanitized_artifact": {
        "operation": "update",
        "precondition": "artifact contains unsanitized content",
        "proposed_change": "Run sanitization pipeline on artifact after manual review",
    },
    "missing_source_of_truth_ref": {
        "operation": "register",
        "precondition": "artifact in SoT scope has no source_of_truth_ref",
        "proposed_change": "Add source_of_truth_ref after manual identification of SoT origin",
    },
    "orphan_registry_entry": {
        "operation": "delete",
        "precondition": "registry entry exists but file missing on disk",
        "proposed_change": "Remove orphan registry entry or restore missing file",
    },
    "unregistered_artifact": {
        "operation": "register",
        "precondition": "file exists on disk but not in registry",
        "proposed_change": "Register artifact in sot_registry.json after manual review",
    },
    "invalid_evidence_ref": {
        "operation": "update",
        "precondition": "evidence_ref exists but is malformed",
        "proposed_change": "Fix evidence_ref structure after manual review",
    },
    "forbidden_public_artifact": {
        "operation": "delete",
        "precondition": "artifact is in forbidden public scope",
        "proposed_change": "No automated fix available — remove artifact from public export manually",
    },
    "fail_open_guard": {
        "operation": "update",
        "precondition": "validator contains fail-open pattern",
        "proposed_change": "No automated fix available — rewrite guard logic to fail-closed",
    },
    "registry_schema_invalid": {
        "operation": "update",
        "precondition": "registry JSON is unparseable or schema-invalid",
        "proposed_change": "No automated fix available — manually repair registry schema",
    },
    "export_scope_violation": {
        "operation": "delete",
        "precondition": "artifact violates export scope boundaries",
        "proposed_change": "No automated fix available — remove from export or adjust scope policy",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_repo_root() -> Path:
    """Auto-detect repo root via git or fallback to file-relative."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return Path(__file__).resolve().parents[2]


def _sha256_file(filepath: Path) -> Optional[str]:
    """SHA256 hex digest of file. Returns None if missing."""
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except (FileNotFoundError, OSError):
        return None


def _sha256_string(s: str) -> str:
    """SHA256 hex digest of a string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _action_id(finding_id: str) -> str:
    """Generate remediation action ID: REM-{finding_id}."""
    return f"REM-{finding_id}"


def _classify_finding(finding_class: str) -> str:
    """Map finding class to remediation class."""
    return FINDING_TO_REMEDIATION.get(finding_class, "manual_review_required")


def _can_auto_fix_missing_evidence(
    finding: Dict[str, Any],
    repo_root: Path,
) -> bool:
    """Check if a missing_evidence_ref finding qualifies for auto-fix.

    Only auto-fixable if the file exists on disk and hash is computable.
    """
    art_path = finding.get("path", "")
    if not art_path:
        return False
    full_path = repo_root / art_path
    return full_path.is_file() and _sha256_file(full_path) is not None


# ---------------------------------------------------------------------------
# Core remediation planner
# ---------------------------------------------------------------------------

def run_remediation_planner(
    findings_path: str,
    repo_root: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run remediation planner on gate findings.

    Args:
        findings_path: Path to findings JSON (single file or run-ledger).
        repo_root: Path to SSID repo root (auto-detected if None).
        output_dir: Output directory for reports (default: <repo-root>/02_audit_logging/reports).

    Returns:
        Structured result dict with gate, status, plan, and summary.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resolved_repo = Path(repo_root).resolve() if repo_root else _detect_repo_root()
    resolved_output = Path(output_dir) if output_dir else resolved_repo / "02_audit_logging" / "reports"

    # --- Load findings ---
    findings_file = Path(findings_path)
    if not findings_file.is_file():
        return _build_error_result(ts, resolved_repo, f"Findings file not found: {findings_path}")

    try:
        raw = json.loads(findings_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return _build_error_result(ts, resolved_repo, f"Failed to parse findings: {exc}")

    # Support both direct findings list and gate result with .findings key
    if isinstance(raw, list):
        findings = raw
    elif isinstance(raw, dict):
        findings = raw.get("findings", [])
    else:
        return _build_error_result(ts, resolved_repo, "Unexpected findings format: expected list or dict")

    if not isinstance(findings, list):
        return _build_error_result(ts, resolved_repo, "Findings field is not a list")

    # --- Classify and build actions ---
    actions: List[Dict[str, Any]] = []
    class_counts: Dict[str, int] = {
        "auto_fix_safe": 0,
        "manual_review_required": 0,
        "hard_block_no_fix": 0,
    }

    for finding in findings:
        finding_class = finding.get("class", "unknown")
        finding_id = finding.get("id", f"UNKNOWN-{_sha256_string(json.dumps(finding, sort_keys=True))[:8]}")
        finding_path = finding.get("path", "")

        # Determine remediation class
        rem_class = _classify_finding(finding_class)

        # Special handling: missing_evidence_ref is only auto_fix_safe
        # if file exists and hash is computable
        if finding_class == "missing_evidence_ref" and rem_class == "auto_fix_safe":
            if not _can_auto_fix_missing_evidence(finding, resolved_repo):
                rem_class = "manual_review_required"

        class_counts[rem_class] = class_counts.get(rem_class, 0) + 1

        # Build patch proposal
        defaults = _REMEDIATION_DEFAULTS.get(rem_class, _REMEDIATION_DEFAULTS["manual_review_required"])
        template = _OPERATION_TEMPLATES.get(finding_class, {
            "operation": "update",
            "precondition": "unknown — manual investigation required",
            "proposed_change": "No automated fix available — unknown finding class",
        })

        # Risk escalation for hash_mismatch
        risk = defaults["risk_level"]
        if finding_class == "hash_mismatch":
            risk = "high"

        action: Dict[str, Any] = {
            "action_id": _action_id(finding_id),
            "finding_id": finding_id,
            "finding_class": finding_class,
            "remediation_class": rem_class,
            "file": finding_path,
            "operation": template["operation"],
            "precondition": template["precondition"],
            "proposed_change": template["proposed_change"],
            "risk_level": risk,
            "requires_approval": defaults["requires_approval"],
            "reversible": defaults["reversible"],
        }

        # Enrich auto_fix_safe actions with computed data where possible
        if rem_class == "auto_fix_safe" and finding_path:
            full_path = resolved_repo / finding_path
            if full_path.is_file():
                disk_hash = _sha256_file(full_path)
                if disk_hash:
                    action["computed_hash"] = disk_hash

        actions.append(action)

    # --- Determine overall status ---
    if class_counts.get("hard_block_no_fix", 0) > 0:
        status = "HARD_BLOCK"
    elif class_counts.get("manual_review_required", 0) > 0:
        status = "MANUAL_REVIEW"
    elif class_counts.get("auto_fix_safe", 0) > 0:
        status = "AUTO_FIXABLE"
    else:
        status = "CLEAN"

    return {
        "gate": "remediation_planner",
        "version": "1.0.0",
        "timestamp_utc": ts,
        "status": status,
        "repo": str(resolved_repo),
        "plan": {
            "total_actions": len(actions),
            "actions": actions,
        },
        "summary": {
            "total_findings": len(findings),
            "auto_fix_safe": class_counts.get("auto_fix_safe", 0),
            "manual_review_required": class_counts.get("manual_review_required", 0),
            "hard_block_no_fix": class_counts.get("hard_block_no_fix", 0),
            "by_class": _count_by_class(findings),
        },
    }


def _build_error_result(
    ts: str,
    repo_root: Path,
    error_msg: str,
) -> Dict[str, Any]:
    """Build error result when planner cannot run."""
    return {
        "gate": "remediation_planner",
        "version": "1.0.0",
        "timestamp_utc": ts,
        "status": "ERROR",
        "repo": str(repo_root),
        "plan": {"total_actions": 0, "actions": []},
        "summary": {
            "total_findings": 0,
            "auto_fix_safe": 0,
            "manual_review_required": 0,
            "hard_block_no_fix": 0,
            "error": error_msg,
        },
    }


def _count_by_class(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count findings by class."""
    by_class: Dict[str, int] = {}
    for f in findings:
        cls = f.get("class", "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
    return by_class


# ---------------------------------------------------------------------------
# Auto-apply (only auto_fix_safe actions)
# ---------------------------------------------------------------------------

def _auto_apply(
    result: Dict[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """Apply auto_fix_safe actions. Returns updated result with apply status.

    SECURITY BOUNDARIES:
    - Only auto_fix_safe actions are applied
    - Only format normalization and registry updates
    - NEVER modifies core logic, policies, or guards
    - NEVER overwrites hashes on mismatch
    - NEVER manipulates evidence
    """
    actions = result.get("plan", {}).get("actions", [])
    applied: List[str] = []
    skipped: List[str] = []
    failed: List[Dict[str, str]] = []

    registry_path = repo_root / "24_meta_orchestration" / "registry" / "sot_registry.json"
    registry_modified = False
    registry: Optional[Dict[str, Any]] = None

    # Load registry once if needed
    needs_registry = any(
        a["remediation_class"] == "auto_fix_safe"
        and a["operation"] in ("normalize", "register")
        for a in actions
    )
    if needs_registry and registry_path.is_file():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            registry = None

    for action in actions:
        action_id = action["action_id"]

        # SAFETY: only touch auto_fix_safe
        if action["remediation_class"] != "auto_fix_safe":
            skipped.append(action_id)
            continue

        finding_class = action.get("finding_class", "")

        try:
            if finding_class == "sha256_prefix_normalization" and registry:
                _apply_sha256_normalize(registry, action["file"])
                registry_modified = True
                applied.append(action_id)

            elif finding_class == "evidence_ref_string_to_object" and registry:
                _apply_evidence_ref_normalize(registry, action["file"])
                registry_modified = True
                applied.append(action_id)

            elif finding_class == "missing_evidence_ref" and registry:
                computed_hash = action.get("computed_hash")
                if computed_hash:
                    _apply_add_evidence_ref(registry, action["file"], computed_hash)
                    registry_modified = True
                    applied.append(action_id)
                else:
                    skipped.append(action_id)

            elif finding_class in ("format_inconsistency", "sort_format_inconsistency") and registry:
                # Registry re-sort handled at write time
                registry_modified = True
                applied.append(action_id)

            else:
                skipped.append(action_id)

        except Exception as exc:
            failed.append({"action_id": action_id, "error": str(exc)})

    # Write modified registry
    if registry_modified and registry is not None:
        try:
            registry_path.write_text(
                json.dumps(registry, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            failed.append({"action_id": "REGISTRY_WRITE", "error": str(exc)})

    result["apply_result"] = {
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
    }
    return result


def _apply_sha256_normalize(registry: Dict[str, Any], art_path: str) -> None:
    """Strip sha256: prefix from hash_sha256 in registry entry."""
    artifacts = registry.get("roots", {}).get("sot_artifacts", [])
    for art in artifacts:
        if art.get("path") == art_path:
            raw = art.get("hash_sha256", "")
            if raw.lower().startswith("sha256:"):
                art["hash_sha256"] = raw[7:].lower().strip()
            break


def _apply_evidence_ref_normalize(registry: Dict[str, Any], art_path: str) -> None:
    """Convert evidence_ref string to canonical object."""
    artifacts = registry.get("roots", {}).get("sot_artifacts", [])
    for art in artifacts:
        if art.get("path") == art_path:
            ref = art.get("evidence_ref")
            if isinstance(ref, str):
                art["evidence_ref"] = {
                    "type": "path",
                    "hash": "",
                    "path": ref,
                }
            break


def _apply_add_evidence_ref(
    registry: Dict[str, Any],
    art_path: str,
    computed_hash: str,
) -> None:
    """Add evidence_ref with computed hash to registry entry."""
    artifacts = registry.get("roots", {}).get("sot_artifacts", [])
    for art in artifacts:
        if art.get("path") == art_path:
            if "evidence_ref" not in art:
                art["evidence_ref"] = {
                    "type": "hash",
                    "hash": computed_hash,
                    "path": art_path,
                }
            break


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _plan_to_json(result: Dict[str, Any]) -> str:
    """Render remediation plan as JSON string."""
    return json.dumps(result, indent=2, sort_keys=False)


def _plan_to_md(result: Dict[str, Any]) -> str:
    """Render remediation plan as Markdown report."""
    lines = [
        "# Gate Remediation Plan Report\n",
        f"\nTimestamp: {result['timestamp_utc']}\n",
        f"Status: **{result['status']}**\n",
    ]

    summary = result.get("summary", {})
    lines.append(f"\nTotal findings: {summary.get('total_findings', 0)}\n")
    lines.append(f"Auto-fixable: {summary.get('auto_fix_safe', 0)}\n")
    lines.append(f"Manual review: {summary.get('manual_review_required', 0)}\n")
    lines.append(f"Hard blocks: {summary.get('hard_block_no_fix', 0)}\n")

    # By-class breakdown
    by_class = summary.get("by_class", {})
    if by_class:
        lines.append("\n## Finding Classes\n\n")
        lines.append("| Class | Count |\n")
        lines.append("|-------|-------|\n")
        for cls, count in sorted(by_class.items()):
            lines.append(f"| `{cls}` | {count} |\n")

    # Actions by remediation class
    plan = result.get("plan", {})
    actions = plan.get("actions", [])

    for rem_class, label in [
        ("auto_fix_safe", "Auto-Fix Safe"),
        ("manual_review_required", "Manual Review Required"),
        ("hard_block_no_fix", "Hard Block (No Fix)"),
    ]:
        class_actions = [a for a in actions if a.get("remediation_class") == rem_class]
        if not class_actions:
            continue

        lines.append(f"\n## {label} ({len(class_actions)})\n\n")
        lines.append("| Action ID | File | Operation | Risk | Proposed Change |\n")
        lines.append("|-----------|------|-----------|------|-----------------|\n")
        for a in class_actions:
            change = a.get("proposed_change", "").replace("|", "\\|")
            lines.append(
                f"| `{a['action_id']}` "
                f"| `{a['file']}` "
                f"| {a['operation']} "
                f"| {a['risk_level']} "
                f"| {change} |\n"
            )

    # Apply results if present
    apply_result = result.get("apply_result")
    if apply_result:
        lines.append("\n## Auto-Apply Results\n\n")
        lines.append(f"Applied: {apply_result['applied_count']}\n")
        lines.append(f"Skipped: {apply_result['skipped_count']}\n")
        lines.append(f"Failed: {apply_result['failed_count']}\n")
        if apply_result.get("failed"):
            lines.append("\n### Failures\n\n")
            for f in apply_result["failed"]:
                lines.append(f"- `{f['action_id']}`: {f['error']}\n")

    lines.append(
        f"\n---\n\nGenerated by `run_gate_remediation_planner.py` "
        f"v{result['version']} at {result['timestamp_utc']}\n"
    )

    return "".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_gate_remediation_planner",
        description=(
            "Gate Remediation Planner — classifies gate findings "
            "and generates fix plans"
        ),
    )
    parser.add_argument(
        "--findings-path", type=str, required=True,
        help="Path to findings JSON (gate output or run-ledger)",
    )
    parser.add_argument(
        "--repo-root", type=str, default=None,
        help="Path to SSID repo root (default: auto-detect via git)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Report output directory (default: <repo-root>/02_audit_logging/reports)",
    )
    parser.add_argument(
        "--write-reports", action="store_true",
        help="Write JSON + MD reports to output directory",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Verify only — print result, no reports written, no auto-apply",
    )
    parser.add_argument(
        "--auto-apply", action="store_true",
        help=(
            "Apply auto_fix_safe actions to registry. "
            "ONLY normalizations and registry updates — "
            "never core logic, policies, guards, or evidence"
        ),
    )
    args = parser.parse_args()

    # Resolve paths
    repo_root_str: Optional[str] = args.repo_root
    output_dir_str: Optional[str] = args.output_dir

    # Run planner
    try:
        result = run_remediation_planner(
            findings_path=args.findings_path,
            repo_root=repo_root_str,
            output_dir=output_dir_str,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if result["status"] == "ERROR":
        error_msg = result.get("summary", {}).get("error", "Unknown error")
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return EXIT_ERROR

    # Auto-apply if requested (and not verify-only)
    if args.auto_apply and not args.verify_only:
        resolved_repo = Path(repo_root_str).resolve() if repo_root_str else _detect_repo_root()
        result = _auto_apply(result, resolved_repo)

    # Print summary
    summary = result["summary"]
    print(
        f"REMEDIATION: {result['status']} "
        f"(findings: {summary['total_findings']}, "
        f"auto_fix: {summary['auto_fix_safe']}, "
        f"manual: {summary['manual_review_required']}, "
        f"hard_block: {summary['hard_block_no_fix']})"
    )

    # Print actions grouped by remediation class
    actions = result.get("plan", {}).get("actions", [])
    for action in actions:
        rem_tag = action["remediation_class"].upper()
        print(
            f"  {rem_tag}: {action['action_id']}: "
            f"{action['operation']} {action['file']} — "
            f"{action['proposed_change']}"
        )

    # Print apply results if present
    apply_result = result.get("apply_result")
    if apply_result:
        print(
            f"  APPLIED: {apply_result['applied_count']} "
            f"SKIPPED: {apply_result['skipped_count']} "
            f"FAILED: {apply_result['failed_count']}"
        )
        for f in apply_result.get("failed", []):
            print(f"    FAIL: {f['action_id']}: {f['error']}")

    # Write reports (unless --verify-only)
    if args.write_reports and not args.verify_only:
        resolved_output = (
            Path(output_dir_str) if output_dir_str
            else (Path(repo_root_str).resolve() if repo_root_str else _detect_repo_root())
            / "02_audit_logging" / "reports"
        )
        resolved_output.mkdir(parents=True, exist_ok=True)

        json_path = resolved_output / "remediation_plan.json"
        md_path = resolved_output / "remediation_report.md"
        json_path.write_text(_plan_to_json(result), encoding="utf-8")
        md_path.write_text(_plan_to_md(result), encoding="utf-8")
        print(f"REPORT: {json_path}")
        print(f"REPORT: {md_path}")

    # Exit code
    if result["status"] == "HARD_BLOCK":
        return EXIT_HARD_BLOCK
    elif result["status"] == "MANUAL_REVIEW":
        return EXIT_MANUAL
    elif result["status"] == "ERROR":
        return EXIT_ERROR
    return EXIT_ALL_AUTO


if __name__ == "__main__":
    raise SystemExit(main())
