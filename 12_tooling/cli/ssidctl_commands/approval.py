#!/usr/bin/env python3
"""ssidctl approval -- Show and manage approval queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for approval."""
    if subparsers is not None:
        parser = subparsers.add_parser("approval", help="Show and manage approval queue")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl approval", description=__doc__)
    parser.add_argument(
        "action", nargs="?", default="list", choices=["list", "show", "count"], help="Action to perform (default: list)"
    )
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def _find_approval_artifacts(repo_root: Path) -> list[dict[str, str]]:
    """Find approval-related artifacts in the repository."""
    artifacts: list[dict[str, str]] = []
    for pattern in ("**/approval*.json", "**/approval*.yaml", "**/pending_approval*"):
        for p in sorted(repo_root.glob(pattern)):
            if ".git" not in p.parts:
                artifacts.append(
                    {
                        "path": str(p.relative_to(repo_root)),
                        "status": "pending",
                    }
                )
    return artifacts


def run(args: argparse.Namespace) -> int:
    """Execute approval command."""
    repo_root = Path(args.root).resolve()
    artifacts = _find_approval_artifacts(repo_root)

    result: dict[str, object] = {
        "command": "approval",
        "action": args.action,
        "root": str(repo_root),
        "queue_length": len(artifacts),
        "items": artifacts[:50],
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Approval Queue ({args.action})")
        print(f"  Root:   {repo_root}")
        print(f"  Queue:  {len(artifacts)} item(s)")
        if artifacts:
            for a in artifacts[:20]:
                print(f"  [{a['status']}] {a['path']}")
        else:
            print("  (queue empty)")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
