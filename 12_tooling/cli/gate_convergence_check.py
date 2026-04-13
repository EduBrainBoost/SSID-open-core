#!/usr/bin/env python3
"""Gate Convergence Check -- CI/CD gate wrapper around SoT Convergence Scanner.

Read-only gate that orchestrates:
  1. SoT Convergence Scanner (drift detection)
  2. Convergence Manifest Generator (manifest + report)
  3. Policy evaluation (deterministic exit states)

Never modifies source files. Protected paths are reported, never changed.

Exit codes:
  0 = PASS  -- no drift, all convergence checks passed
  1 = FAIL  -- critical drift or missing artifacts detected
  2 = WARN  -- non-critical drift findings present

Usage:
    python gate_convergence_check.py --repo-root /path/to/SSID
    python gate_convergence_check.py --repo-root . --contract 16_codex/contracts/sot/sot_contract.yaml
    python gate_convergence_check.py --repo-root . --output /tmp/gate_result/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Resolve sibling imports (scanner + manifest gen live in ../validation/)
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_VALIDATION_DIR = _THIS_DIR.parent / "validation"

if str(_VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(_VALIDATION_DIR))

try:
    from sot_convergence_scanner import scan as scanner_scan  # type: ignore[import]
except ImportError:
    sys.exit(
        f"ERROR: Cannot import sot_convergence_scanner. Expected at: {_VALIDATION_DIR / 'sot_convergence_scanner.py'}"
    )

try:
    from convergence_manifest_gen import (  # type: ignore[import]
        SchemaError,
        generate_manifest,
        render_report,
    )
except ImportError:
    sys.exit(
        f"ERROR: Cannot import convergence_manifest_gen. Expected at: {_VALIDATION_DIR / 'convergence_manifest_gen.py'}"
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_WARN = 2

DEFAULT_CONTRACT_REL = "16_codex/contracts/sot/sot_contract.yaml"
DEFAULT_REPO_ROLE = "canonical"

# Severity levels that trigger FAIL (not just WARN)
_FAIL_SEVERITIES = frozenset({"critical", "high"})

# Drift classes that always trigger FAIL regardless of severity
_FAIL_CLASSES = frozenset(
    {
        "missing_required_artifact",
        "registry_missing",
        "protected_scope_attempt",
        "export_violation",
    }
)

# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------


def _evaluate_policy(scan_result: dict[str, Any]) -> tuple[int, str]:
    """Evaluate scan result against gate policy.

    Returns (exit_code, reason_summary).
    """
    status = scan_result.get("status", "UNKNOWN")
    findings = scan_result.get("drift_findings", [])
    blocked = scan_result.get("blocked_operations", [])
    missing = scan_result.get("missing_artifacts", [])

    # Hard FAIL conditions
    if status == "FAIL":
        # Check if it's truly critical or just warn-level
        has_critical = any(f.get("severity") in _FAIL_SEVERITIES or f.get("class") in _FAIL_CLASSES for f in findings)
        if has_critical:
            reasons = []
            if missing:
                reasons.append(f"{len(missing)} missing critical artifact(s)")
            critical_findings = [
                f for f in findings if f.get("severity") in _FAIL_SEVERITIES or f.get("class") in _FAIL_CLASSES
            ]
            if critical_findings:
                reasons.append(f"{len(critical_findings)} critical/high finding(s)")
            if blocked:
                reasons.append(f"{len(blocked)} blocked operation(s)")
            # Check for protected scope attempts specifically
            protected = [f for f in findings if f.get("class") == "protected_scope_attempt"]
            if protected:
                reasons.append(f"{len(protected)} protected scope attempt(s)")
            return EXIT_FAIL, "; ".join(reasons) if reasons else "FAIL status from scanner"

        # Only non-critical findings -> WARN
        return EXIT_WARN, f"{len(findings)} non-critical drift finding(s)"

    if status == "PASS":
        return EXIT_PASS, "All convergence checks passed"

    # Unknown status -> FAIL as safety default
    return EXIT_FAIL, f"Unknown scanner status: {status}"


# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------


def _sha256_string(data: str) -> str:
    """Return hex SHA-256 of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Gate report (structured JSON output)
# ---------------------------------------------------------------------------


def _build_gate_report(
    scan_result: dict[str, Any],
    manifest_json: str,
    report_md: str,
    exit_code: int,
    reason: str,
) -> dict[str, Any]:
    """Build the gate-level report wrapping scan + manifest + policy."""
    exit_label = {EXIT_PASS: "PASS", EXIT_FAIL: "FAIL", EXIT_WARN: "WARN"}.get(exit_code, "UNKNOWN")

    return {
        "gate_name": "gate_convergence_check",
        "gate_version": "1.0.0",
        "run_time_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exit_code": exit_code,
        "exit_label": exit_label,
        "reason": reason,
        "scan_result": scan_result,
        "evidence_artifacts": {
            "manifest_sha256": _sha256_string(manifest_json),
            "report_sha256": _sha256_string(report_md),
        },
        "policy_evaluation": {
            "fail_conditions_checked": [
                "status==FAIL",
                "missing_critical_artifacts",
                "protected_scope_attempt",
            ],
            "warn_conditions_checked": [
                "drift_findings_present",
                "non_critical_missing",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Main gate logic
# ---------------------------------------------------------------------------


def run_gate(
    repo_root: str,
    contract_path: str | None = None,
    repo_role: str = DEFAULT_REPO_ROLE,
    output_dir: str | None = None,
) -> int:
    """Execute the full gate convergence check pipeline.

    Returns the exit code (0=PASS, 1=FAIL, 2=WARN).
    """
    root = Path(repo_root).resolve()

    # Resolve contract path
    if contract_path is None:
        contract_path = DEFAULT_CONTRACT_REL
    contract = Path(contract_path)
    if not contract.is_absolute():
        contract = root / contract

    if not contract.is_file():
        print(
            f"FAIL: Contract file not found: {contract}",
            file=sys.stderr,
        )
        return EXIT_FAIL

    # --- Step 1: Run scanner ---
    try:
        scan_result = scanner_scan(
            canonical_contract_path=str(contract),
            target_repo_root=str(root),
            repo_role=repo_role,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"FAIL: Scanner error: {exc}", file=sys.stderr)
        return EXIT_FAIL

    # --- Step 2: Generate manifest ---
    try:
        manifest_json = generate_manifest(scan_result)
    except SchemaError as exc:
        print(f"FAIL: Manifest generation error: {exc}", file=sys.stderr)
        return EXIT_FAIL

    # --- Step 3: Generate report ---
    report_md = render_report(scan_result)

    # --- Step 4: Evaluate policy ---
    exit_code, reason = _evaluate_policy(scan_result)

    # --- Step 5: Build gate report ---
    gate_report = _build_gate_report(
        scan_result=scan_result,
        manifest_json=manifest_json,
        report_md=report_md,
        exit_code=exit_code,
        reason=reason,
    )
    gate_report_json = json.dumps(gate_report, indent=2, sort_keys=True, ensure_ascii=False)

    # --- Step 6: Output ---
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        (out / "convergence_manifest.json").write_text(manifest_json + "\n", encoding="utf-8")
        (out / "convergence_report.md").write_text(report_md, encoding="utf-8")
        (out / "gate_report.json").write_text(gate_report_json + "\n", encoding="utf-8")

        print(f"Gate artifacts written to: {out}", file=sys.stderr)
        print(
            f"  convergence_manifest.json  SHA-256: {gate_report['evidence_artifacts']['manifest_sha256'][:16]}...",
            file=sys.stderr,
        )
        print(
            f"  convergence_report.md      SHA-256: {gate_report['evidence_artifacts']['report_sha256'][:16]}...",
            file=sys.stderr,
        )
    else:
        # Print gate report to stdout
        print(gate_report_json)

    # Print summary to stderr
    exit_label = gate_report["exit_label"]
    print(f"\nGate result: {exit_label} -- {reason}", file=sys.stderr)

    return exit_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Gate Convergence Check -- CI/CD gate for SoT convergence. "
            "Read-only, deterministic exit codes: 0=PASS, 1=FAIL, 2=WARN."
        ),
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        help="Root of the SSID repository to check",
    )
    parser.add_argument(
        "--contract",
        default=None,
        help=(f"Path to sot_contract.yaml (default: <repo-root>/{DEFAULT_CONTRACT_REL})"),
    )
    parser.add_argument(
        "--repo-role",
        default=DEFAULT_REPO_ROLE,
        choices=("canonical", "derivative", "orchestration"),
        help="Repository role (default: canonical)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output directory for gate artifacts "
            "(convergence_manifest.json, convergence_report.md, gate_report.json). "
            "If omitted, gate report is printed to stdout."
        ),
    )
    args = parser.parse_args(argv)

    exit_code = run_gate(
        repo_root=args.repo_root,
        contract_path=args.contract,
        repo_role=args.repo_role,
        output_dir=args.output,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
