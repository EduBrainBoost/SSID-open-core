#!/usr/bin/env python3
"""ssidctl resilience -- Resilience status and drill management."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for resilience."""
    if subparsers is not None:
        parser = subparsers.add_parser("resilience", help="Resilience status and drill management")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl resilience", description=__doc__)
    parser.add_argument("action", nargs="?", default="status",
                        choices=["status", "drill-list", "drill-history"],
                        help="Action to perform (default: status)")
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def _check_resilience_artifacts(repo_root: Path) -> dict[str, object]:
    """Check resilience-related artifacts."""
    infra_dir = repo_root / "15_infra"
    observability_dir = repo_root / "17_observability"
    return {
        "infra_present": infra_dir.is_dir(),
        "observability_present": observability_dir.is_dir(),
        "drill_history": [],
        "last_drill": None,
    }


def run(args: argparse.Namespace) -> int:
    """Execute resilience command."""
    repo_root = Path(args.root).resolve()
    artifacts = _check_resilience_artifacts(repo_root)
    timestamp = datetime.now(timezone.utc).isoformat()

    result: dict[str, object] = {
        "command": "resilience",
        "action": args.action,
        "timestamp": timestamp,
        "root": str(repo_root),
        **artifacts,
        "status": "nominal",
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Resilience [{args.action}]")
        print(f"  Root:            {repo_root}")
        print(f"  Infra Dir:       {'found' if artifacts['infra_present'] else 'MISSING'}")
        print(f"  Observability:   {'found' if artifacts['observability_present'] else 'MISSING'}")
        print(f"  Status:          nominal")
        if args.action == "drill-list":
            print("  Drills:          (none scheduled)")
        elif args.action == "drill-history":
            print("  History:         (no drills recorded)")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
