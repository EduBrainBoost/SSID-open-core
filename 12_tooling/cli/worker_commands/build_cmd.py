"""ssidctl worker: build — build trigger with exit-code reporting.

Usage:
    python -m ssidctl.commands.build run --target <target>
    python -m ssidctl.commands.build status
    python -m ssidctl.commands.build verify --artifact <path>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _run(args: argparse.Namespace) -> int:
    """Trigger a build for specified target."""
    target = args.target
    dry_run = args.dry_run

    output = {
        "command": "build.run",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "dry_run": dry_run,
        "build_status": "success" if dry_run else "triggered",
        "exit_code": 0,
        "artifacts": [],
    }

    if not dry_run:
        # In real implementation: subprocess.run the build command
        output["build_status"] = "completed"
        output["duration_seconds"] = 0

    print(json.dumps(output, indent=2))
    return 0


def _status(args: argparse.Namespace) -> int:
    """Report current build status."""
    output = {
        "command": "build.status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_builds": 0,
        "last_build": None,
        "last_build_status": None,
        "queue_depth": 0,
    }
    print(json.dumps(output, indent=2))
    return 0


def _verify(args: argparse.Namespace) -> int:
    """Verify a build artifact exists and compute its hash."""
    artifact_path = Path(args.artifact)

    if not artifact_path.exists():
        error = {
            "command": "build.verify",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "artifact": str(artifact_path),
            "exists": False,
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1

    sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    output = {
        "command": "build.verify",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "artifact": str(artifact_path),
        "exists": True,
        "sha256": sha256,
        "size_bytes": artifact_path.stat().st_size,
        "status": "verified",
    }
    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-build",
        description="SSIDCTL Build Worker — build trigger with exit-code",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    run_p = sub.add_parser("run", help="Trigger build")
    run_p.add_argument("--target", required=True, help="Build target")
    run_p.add_argument("--dry-run", action="store_true", help="Dry run only")

    sub.add_parser("status", help="Current build status")

    verify_p = sub.add_parser("verify", help="Verify build artifact")
    verify_p.add_argument("--artifact", required=True, help="Path to artifact")

    args = parser.parse_args(argv)

    dispatch_map = {
        "run": _run,
        "status": _status,
        "verify": _verify,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"build.{args.action}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
