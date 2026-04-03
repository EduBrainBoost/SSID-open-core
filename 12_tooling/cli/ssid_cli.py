#!/usr/bin/env python3
"""
SSID CLI — Unified entry point for SSID tooling commands.

Commands:
  health    Check all services and infrastructure status
  gates     Run the gate chain pipeline
  validate  Run the SoT validator
  evidence  List or verify evidence files
  report    Generate a status report

Usage:
  python 12_tooling/cli/ssid_cli.py health [--json]
  python 12_tooling/cli/ssid_cli.py gates [--dry-run]
  python 12_tooling/cli/ssid_cli.py validate [--verify-all]
  python 12_tooling/cli/ssid_cli.py evidence [--verify] [--dir DIR]
  python 12_tooling/cli/ssid_cli.py report [--output FILE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Windows cp1252 safety
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

# Canonical root folders (ROOT-24-LOCK)
CANONICAL_ROOTS = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto", "22_datasets",
    "23_compliance", "24_meta_orchestration",
]

EVIDENCE_DIR = REPO_ROOT / ".ssid-system" / "evidence"
AGENT_RUNS_DIR = REPO_ROOT / "02_audit_logging" / "agent_runs"


# ---------------------------------------------------------------------------
# health command
# ---------------------------------------------------------------------------

def _check_root_structure() -> dict[str, bool]:
    """Check that all 24 canonical roots exist."""
    results = {}
    for root in CANONICAL_ROOTS:
        results[root] = (REPO_ROOT / root).is_dir()
    return results


def _check_git_status() -> dict[str, Any]:
    """Return basic git health info."""
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
        )
        return {
            "branch": branch.stdout.strip(),
            "clean": len(status.stdout.strip()) == 0,
            "dirty_files": len(status.stdout.strip().splitlines()) if status.stdout.strip() else 0,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _check_evidence_dir() -> dict[str, Any]:
    """Check evidence directory health."""
    if not EVIDENCE_DIR.is_dir():
        return {"exists": False, "entries": 0}
    entries = list(EVIDENCE_DIR.rglob("*.json"))
    return {"exists": True, "entries": len(entries)}


def cmd_health(args: argparse.Namespace) -> int:
    """Run health checks on all services."""
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "root_structure": _check_root_structure(),
        "git": _check_git_status(),
        "evidence": _check_evidence_dir(),
    }

    roots_ok = all(report["root_structure"].values())
    git_ok = report["git"].get("clean", False) or "error" not in report["git"]
    evidence_ok = report["evidence"].get("exists", False)

    report["summary"] = {
        "roots_ok": roots_ok,
        "git_ok": git_ok,
        "evidence_ok": evidence_ok,
        "overall": "PASS" if (roots_ok and git_ok and evidence_ok) else "WARN",
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== SSID Health Check ===")
        missing = [k for k, v in report["root_structure"].items() if not v]
        print(f"Root folders: {24 - len(missing)}/24 present"
              + (f" (missing: {', '.join(missing)})" if missing else ""))
        git = report["git"]
        if "error" in git:
            print(f"Git: ERROR — {git['error']}")
        else:
            print(f"Git: branch={git['branch']}, clean={git['clean']}, dirty={git['dirty_files']}")
        ev = report["evidence"]
        print(f"Evidence: exists={ev['exists']}, entries={ev['entries']}")
        print(f"Overall: {report['summary']['overall']}")

    return 0 if report["summary"]["overall"] == "PASS" else 1


# ---------------------------------------------------------------------------
# gates command
# ---------------------------------------------------------------------------

def cmd_gates(args: argparse.Namespace) -> int:
    """Run the gate chain pipeline."""
    gate_script = SCRIPT_DIR / "run_all_gates.py"
    if not gate_script.is_file():
        print(f"ERROR: Gate pipeline not found at {gate_script}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(gate_script)]
    if args.dry_run:
        print(f"DRY-RUN: would execute {' '.join(cmd)}")
        return 0

    print(f"Running gate pipeline: {gate_script.name}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode


# ---------------------------------------------------------------------------
# validate command
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    """Run the SoT validator."""
    # Prefer canonical core validator, fall back to CLI copy
    core_validator = REPO_ROOT / "03_core" / "validators" / "sot" / "sot_validator_core.py"
    cli_validator = SCRIPT_DIR / "sot_validator.py"

    validator = core_validator if core_validator.is_file() else cli_validator
    if not validator.is_file():
        print("ERROR: No SoT validator found", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(validator)]
    if args.verify_all:
        cmd.append("--verify-all")

    print(f"Running SoT validator: {validator.name}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode


# ---------------------------------------------------------------------------
# evidence command
# ---------------------------------------------------------------------------

def cmd_evidence(args: argparse.Namespace) -> int:
    """List or verify evidence files."""
    evidence_dir = Path(args.dir) if args.dir else EVIDENCE_DIR

    if not evidence_dir.is_dir():
        print(f"ERROR: Evidence directory not found: {evidence_dir}", file=sys.stderr)
        return 1

    entries = sorted(evidence_dir.rglob("*.json"))
    if not entries:
        print("No evidence files found.")
        return 0

    if args.verify:
        # Use the evidence_verifier module
        try:
            from evidence_verifier import verify_chain
            results = verify_chain(str(evidence_dir))
            passed = sum(1 for r in results if r["status"] == "PASS")
            failed = len(results) - passed
            for r in results:
                marker = "PASS" if r["status"] == "PASS" else "FAIL"
                print(f"  [{marker}] {r['file']}")
            print(f"\nTotal: {len(results)} | PASS: {passed} | FAIL: {failed}")
            return 0 if failed == 0 else 1
        except ImportError:
            print("WARN: evidence_verifier not importable, falling back to listing")

    print(f"Evidence entries in {evidence_dir}:")
    for entry in entries:
        rel = entry.relative_to(REPO_ROOT) if entry.is_relative_to(REPO_ROOT) else entry
        size = entry.stat().st_size
        print(f"  {rel} ({size} bytes)")
    print(f"\nTotal: {len(entries)} files")
    return 0


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    """Generate a status report."""
    report_lines: list[str] = []
    ts = datetime.now(timezone.utc).isoformat()

    report_lines.append(f"# SSID Status Report")
    report_lines.append(f"Generated: {ts}")
    report_lines.append("")

    # Root structure
    roots = _check_root_structure()
    present = sum(1 for v in roots.values() if v)
    report_lines.append(f"## Root Structure: {present}/24")
    missing = [k for k, v in roots.items() if not v]
    if missing:
        for m in missing:
            report_lines.append(f"  - MISSING: {m}")
    report_lines.append("")

    # Git status
    git = _check_git_status()
    report_lines.append("## Git Status")
    if "error" in git:
        report_lines.append(f"  Error: {git['error']}")
    else:
        report_lines.append(f"  Branch: {git['branch']}")
        report_lines.append(f"  Clean: {git['clean']}")
        report_lines.append(f"  Dirty files: {git['dirty_files']}")
    report_lines.append("")

    # Evidence
    ev = _check_evidence_dir()
    report_lines.append("## Evidence")
    report_lines.append(f"  Directory exists: {ev['exists']}")
    report_lines.append(f"  Entries: {ev['entries']}")
    report_lines.append("")

    content = "\n".join(report_lines) + "\n"

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Report written to {out_path}")
    else:
        print(content)

    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ssid-cli",
        description="SSID Unified CLI — health, gates, validate, evidence, report",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # health
    p_health = subparsers.add_parser("health", help="Check all services")
    p_health.add_argument("--json", action="store_true", help="Output JSON format")
    p_health.set_defaults(func=cmd_health)

    # gates
    p_gates = subparsers.add_parser("gates", help="Run gate chain pipeline")
    p_gates.add_argument("--dry-run", action="store_true", help="Print commands without running")
    p_gates.set_defaults(func=cmd_gates)

    # validate
    p_validate = subparsers.add_parser("validate", help="Run SoT validator")
    p_validate.add_argument("--verify-all", action="store_true", help="Full verification")
    p_validate.set_defaults(func=cmd_validate)

    # evidence
    p_evidence = subparsers.add_parser("evidence", help="List/verify evidence files")
    p_evidence.add_argument("--verify", action="store_true", help="Verify evidence chain integrity")
    p_evidence.add_argument("--dir", type=str, default=None, help="Evidence directory override")
    p_evidence.set_defaults(func=cmd_evidence)

    # report
    p_report = subparsers.add_parser("report", help="Generate status report")
    p_report.add_argument("--output", type=str, default=None, help="Output file path")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
