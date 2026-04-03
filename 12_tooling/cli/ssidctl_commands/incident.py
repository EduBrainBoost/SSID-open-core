#!/usr/bin/env python3
"""ssidctl incident -- Incident management CLI."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for incident."""
    if subparsers is not None:
        parser = subparsers.add_parser("incident", help="Incident management CLI")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl incident", description=__doc__)
    parser.add_argument("action", nargs="?", default="list",
                        choices=["list", "count", "summary"],
                        help="Action to perform (default: list)")
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--severity", choices=["low", "medium", "high", "critical"],
                        help="Filter by severity")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def _scan_incident_artifacts(repo_root: Path) -> list[dict[str, str]]:
    """Scan for incident-related files."""
    incidents: list[dict[str, str]] = []
    for pattern in ("**/incident*", "**/incidents/**"):
        for p in sorted(repo_root.glob(pattern)):
            if ".git" not in p.parts and p.is_file():
                incidents.append({
                    "path": str(p.relative_to(repo_root)),
                    "status": "open",
                })
    return incidents


def run(args: argparse.Namespace) -> int:
    """Execute incident command."""
    repo_root = Path(args.root).resolve()
    incidents = _scan_incident_artifacts(repo_root)
    timestamp = datetime.now(timezone.utc).isoformat()

    result: dict[str, object] = {
        "command": "incident",
        "action": args.action,
        "timestamp": timestamp,
        "root": str(repo_root),
        "severity_filter": args.severity,
        "incidents_found": len(incidents),
        "incidents": incidents[:50],
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Incident Management [{args.action}]")
        print(f"  Root:      {repo_root}")
        print(f"  Filter:    severity={args.severity or 'all'}")
        print(f"  Found:     {len(incidents)} incident artifact(s)")
        if args.action == "list":
            for inc in incidents[:20]:
                print(f"  [{inc['status']}] {inc['path']}")
        elif args.action == "count":
            print(f"  Total:     {len(incidents)}")
        elif args.action == "summary":
            print(f"  Open:      {len(incidents)}")
            print(f"  Closed:    0")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
