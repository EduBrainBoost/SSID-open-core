"""ssidctl worker: test — test runner wrapper.

Usage:
    python -m ssidctl.commands.test run --suite <suite_name>
    python -m ssidctl.commands.test status
    python -m ssidctl.commands.test report --format json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime


def _run(args: argparse.Namespace) -> int:
    """Run a test suite."""
    suite = args.suite
    dry_run = args.dry_run

    output = {
        "command": "test.run",
        "timestamp": datetime.now(UTC).isoformat(),
        "suite": suite,
        "dry_run": dry_run,
        "test_status": "skipped" if dry_run else "triggered",
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0,
        "exit_code": 0,
    }

    if not dry_run:
        # In real implementation: subprocess.run pytest with the suite
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--co", "-q", suite],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output["test_status"] = "collected"
            output["exit_code"] = result.returncode
        except (subprocess.TimeoutExpired, FileNotFoundError):
            output["test_status"] = "collection_failed"
            output["exit_code"] = 1

    print(json.dumps(output, indent=2))
    return output.get("exit_code", 0)


def _status(args: argparse.Namespace) -> int:
    """Report test runner status."""
    output = {
        "command": "test.status",
        "timestamp": datetime.now(UTC).isoformat(),
        "runner": "pytest",
        "active_runs": 0,
        "last_run": None,
        "last_result": None,
    }
    print(json.dumps(output, indent=2))
    return 0


def _report(args: argparse.Namespace) -> int:
    """Generate test report."""
    fmt = args.format
    output = {
        "command": "test.report",
        "timestamp": datetime.now(UTC).isoformat(),
        "format": fmt,
        "suites": [],
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "coverage_percent": None,
    }
    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-test",
        description="SSIDCTL Test Worker — test runner wrapper",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    run_p = sub.add_parser("run", help="Run test suite")
    run_p.add_argument("--suite", required=True, help="Test suite name or path")
    run_p.add_argument("--dry-run", action="store_true", help="Dry run only")

    sub.add_parser("status", help="Test runner status")

    report_p = sub.add_parser("report", help="Generate test report")
    report_p.add_argument("--format", default="json", choices=["json", "junit", "markdown"])

    args = parser.parse_args(argv)

    dispatch_map = {
        "run": _run,
        "status": _status,
        "report": _report,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"test.{args.action}",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
