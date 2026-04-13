"""ssidctl worker: release — release gate check.

Usage:
    python -m ssidctl.commands.release check --version <version>
    python -m ssidctl.commands.release gate --gate <gate_name>
    python -m ssidctl.commands.release status
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

RELEASE_GATES = [
    "tests_pass",
    "policy_clean",
    "audit_evidence_complete",
    "registry_consistent",
    "no_secrets_leaked",
    "root_24_intact",
    "provider_health_ok",
    "build_artifacts_verified",
]


def _check(args: argparse.Namespace) -> int:
    """Run all release gates for a version."""
    version = args.version

    gate_results = {}
    for gate in RELEASE_GATES:
        gate_results[gate] = {
            "status": "not_evaluated",
            "note": "Gate stub — requires live evaluation",
        }

    all_pass = all(r["status"] == "pass" for r in gate_results.values())

    output = {
        "command": "release.check",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "gates_total": len(RELEASE_GATES),
        "gates_pass": sum(1 for r in gate_results.values() if r["status"] == "pass"),
        "gates_fail": sum(1 for r in gate_results.values() if r["status"] == "fail"),
        "gates_pending": sum(1 for r in gate_results.values() if r["status"] == "not_evaluated"),
        "gate_results": gate_results,
        "release_allowed": all_pass,
        "status": "go" if all_pass else "no-go",
    }
    print(json.dumps(output, indent=2))
    return 0 if all_pass else 1


def _gate(args: argparse.Namespace) -> int:
    """Evaluate a single release gate."""
    gate_name = args.gate

    if gate_name not in RELEASE_GATES:
        error = {
            "command": "release.gate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gate": gate_name,
            "error": f"Unknown gate. Known: {RELEASE_GATES}",
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1

    output = {
        "command": "release.gate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gate": gate_name,
        "result": "not_evaluated",
        "note": "Single gate stub — requires live evaluation",
    }
    print(json.dumps(output, indent=2))
    return 0


def _status(args: argparse.Namespace) -> int:
    """Report release worker status."""
    output = {
        "command": "release.status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "defined_gates": RELEASE_GATES,
        "gate_count": len(RELEASE_GATES),
        "last_release": None,
        "mode": "NON_INTERACTIVE",
    }
    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-release",
        description="SSIDCTL Release Worker — release gate check",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    check_p = sub.add_parser("check", help="Run all release gates")
    check_p.add_argument("--version", required=True, help="Release version")

    gate_p = sub.add_parser("gate", help="Evaluate single gate")
    gate_p.add_argument("--gate", required=True, help="Gate name")

    sub.add_parser("status", help="Release worker status")

    args = parser.parse_args(argv)

    dispatch_map = {
        "check": _check,
        "gate": _gate,
        "status": _status,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"release.{args.action}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
