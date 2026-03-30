#!/usr/bin/env python3
"""Convergence Manifest Generator.

Takes a scanner result (from sot_convergence_scanner) and:
  1. Validates it against the convergence manifest schema.
  2. Produces deterministic JSON output (sorted keys, indent=2).
  3. Renders a human-readable Markdown report.

Outputs are written to stdout or to file arguments -- never modifies
source files.

Usage:
    # Pipe from scanner
    python sot_convergence_scanner.py ... | python convergence_manifest_gen.py

    # From file
    python convergence_manifest_gen.py --input scan_result.json

    # With explicit output paths
    python convergence_manifest_gen.py --input scan_result.json \\
        --manifest-out manifest.json \\
        --report-out report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Embedded schema -- convergence_manifest_schema.json equivalent
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = {
    "repo_name": str,
    "repo_role": str,
    "scan_time_utc": str,
    "contract_path": str,
    "contract_version": str,
    "contract_sha256": str,
    "rule_count": int,
    "expected_artifacts": list,
    "actual_artifacts": list,
    "missing_artifacts": list,
    "drift_findings": list,
    "blocked_operations": list,
    "export_ready": bool,
    "status": str,
}

_VALID_STATUSES = ("PASS", "FAIL")
_VALID_ROLES = ("canonical", "derivative", "orchestration")

_DRIFT_FINDING_REQUIRED = {"class", "path", "severity", "detail"}
_BLOCKED_OP_REQUIRED = {"operation", "reason"}


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class SchemaError(Exception):
    """Raised when scanner result does not conform to expected schema."""


def validate_result(result: Dict[str, Any]) -> List[str]:
    """Validate a scanner result dict against the manifest schema.

    Returns a list of error strings. Empty list means valid.
    """
    errors: List[str] = []

    # Required top-level fields and types
    for field, expected_type in _REQUIRED_FIELDS.items():
        if field not in result:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(result[field], expected_type):
            errors.append(
                f"Field '{field}' must be {expected_type.__name__}, "
                f"got {type(result[field]).__name__}"
            )

    # Status enum
    if result.get("status") not in _VALID_STATUSES:
        errors.append(
            f"Field 'status' must be one of {_VALID_STATUSES}, "
            f"got '{result.get('status')}'"
        )

    # Repo role enum
    if result.get("repo_role") not in _VALID_ROLES:
        errors.append(
            f"Field 'repo_role' must be one of {_VALID_ROLES}, "
            f"got '{result.get('repo_role')}'"
        )

    # drift_findings item schema
    for i, finding in enumerate(result.get("drift_findings", [])):
        if not isinstance(finding, dict):
            errors.append(f"drift_findings[{i}] must be a dict")
            continue
        missing_keys = _DRIFT_FINDING_REQUIRED - finding.keys()
        if missing_keys:
            errors.append(
                f"drift_findings[{i}] missing keys: {sorted(missing_keys)}"
            )

    # blocked_operations item schema
    for i, op in enumerate(result.get("blocked_operations", [])):
        if not isinstance(op, dict):
            errors.append(f"blocked_operations[{i}] must be a dict")
            continue
        missing_keys = _BLOCKED_OP_REQUIRED - op.keys()
        if missing_keys:
            errors.append(
                f"blocked_operations[{i}] missing keys: {sorted(missing_keys)}"
            )

    # rule_count must be non-negative
    rc = result.get("rule_count")
    if isinstance(rc, int) and rc < 0:
        errors.append("rule_count must be >= 0")

    return errors


# ---------------------------------------------------------------------------
# Manifest generation (deterministic JSON)
# ---------------------------------------------------------------------------


def generate_manifest(result: Dict[str, Any]) -> str:
    """Validate and return deterministic JSON string of the manifest.

    Raises SchemaError if validation fails.
    """
    errors = validate_result(result)
    if errors:
        raise SchemaError(
            "Scanner result failed schema validation:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    manifest = {
        "manifest_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "scan_result": result,
    }
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Markdown report rendering
# ---------------------------------------------------------------------------


def _severity_icon(severity: str) -> str:
    """Return a plain-text severity marker."""
    return {
        "critical": "[CRITICAL]",
        "high": "[HIGH]",
        "medium": "[MEDIUM]",
        "low": "[LOW]",
    }.get(severity.lower(), f"[{severity.upper()}]")


def render_report(result: Dict[str, Any]) -> str:
    """Render a Markdown report from the scanner result."""
    lines: List[str] = []

    status = result.get("status", "UNKNOWN")
    lines.append(f"# SoT Convergence Report -- {status}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Repo | `{result.get('repo_name', '?')}` |")
    lines.append(f"| Role | `{result.get('repo_role', '?')}` |")
    lines.append(f"| Scan time (UTC) | `{result.get('scan_time_utc', '?')}` |")
    lines.append(f"| Contract | `{result.get('contract_path', '?')}` |")
    lines.append(f"| Contract version | `{result.get('contract_version', '?')}` |")
    lines.append(f"| Contract SHA-256 | `{result.get('contract_sha256', '?')[:16]}...` |")
    lines.append(f"| Rule count | {result.get('rule_count', '?')} |")
    lines.append(f"| Expected artifacts | {len(result.get('expected_artifacts', []))} |")
    lines.append(f"| Actual artifacts | {len(result.get('actual_artifacts', []))} |")
    lines.append(f"| Missing artifacts | {len(result.get('missing_artifacts', []))} |")
    lines.append(f"| Drift findings | {len(result.get('drift_findings', []))} |")
    lines.append(f"| Export ready | `{result.get('export_ready', '?')}` |")
    lines.append(f"| Status | **{status}** |")
    lines.append("")

    # Missing artifacts
    missing = result.get("missing_artifacts", [])
    if missing:
        lines.append("## Missing Artifacts")
        lines.append("")
        for m in missing:
            lines.append(f"- `{m}`")
        lines.append("")

    # Drift findings
    findings = result.get("drift_findings", [])
    if findings:
        lines.append("## Drift Findings")
        lines.append("")
        lines.append("| # | Class | Severity | Path | Detail |")
        lines.append("|---|-------|----------|------|--------|")
        for i, f in enumerate(findings, 1):
            sev = _severity_icon(f.get("severity", "?"))
            lines.append(
                f"| {i} | `{f.get('class', '?')}` | {sev} "
                f"| `{f.get('path', '?')}` | {f.get('detail', '')} |"
            )
        lines.append("")

    # Blocked operations
    blocked = result.get("blocked_operations", [])
    if blocked:
        lines.append("## Blocked Operations")
        lines.append("")
        for b in blocked:
            lines.append(f"- **{b.get('operation', '?')}**: {b.get('reason', '')}")
        lines.append("")

    # Footer
    if not findings and not missing:
        lines.append("No drift detected. All convergence checks passed.")
        lines.append("")

    lines.append("---")
    lines.append(
        f"*Generated by convergence_manifest_gen.py at "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}*"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Convergence Manifest Generator",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Scanner result JSON file (default: read from stdin)",
    )
    parser.add_argument(
        "--manifest-out",
        default=None,
        help="Write manifest JSON to file (default: stdout)",
    )
    parser.add_argument(
        "--report-out",
        default=None,
        help="Write Markdown report to file (default: not generated unless specified)",
    )
    parser.add_argument(
        "--report-stdout",
        action="store_true",
        help="Print Markdown report to stdout instead of manifest",
    )
    args = parser.parse_args(argv)

    # Load input
    if args.input:
        result = json.loads(
            Path(args.input).read_text(encoding="utf-8")
        )
    else:
        result = json.load(sys.stdin)

    # Generate manifest
    try:
        manifest_json = generate_manifest(result)
    except SchemaError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    # Write manifest
    if args.manifest_out:
        out = Path(args.manifest_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(manifest_json + "\n", encoding="utf-8")
        print(f"Manifest written to {out}", file=sys.stderr)
    elif not args.report_stdout:
        print(manifest_json)

    # Render report
    if args.report_out or args.report_stdout:
        report_md = render_report(result)
        if args.report_out:
            rp = Path(args.report_out)
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(report_md, encoding="utf-8")
            print(f"Report written to {rp}", file=sys.stderr)
        if args.report_stdout:
            print(report_md)

    sys.exit(0)


if __name__ == "__main__":
    main()
