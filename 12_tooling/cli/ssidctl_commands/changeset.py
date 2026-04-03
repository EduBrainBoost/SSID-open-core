#!/usr/bin/env python3
"""ssidctl changeset -- Show current changesets and their status."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for changeset."""
    if subparsers is not None:
        parser = subparsers.add_parser("changeset", help="Show current changesets and their status")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl changeset", description=__doc__)
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--limit", type=int, default=10, help="Max number of changesets to show")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def _get_recent_commits(root: str, limit: int) -> list[dict[str, str]]:
    """Get recent git commits as changesets."""
    try:
        out = subprocess.run(
            ["git", "log", f"--max-count={limit}", "--pretty=format:%H|%ai|%s"],
            capture_output=True, text=True, cwd=root, timeout=10,
        )
        if out.returncode != 0:
            return []
    except (subprocess.SubprocessError, FileNotFoundError):
        return []

    changesets: list[dict[str, str]] = []
    for line in out.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            changesets.append({
                "sha": parts[0][:12],
                "date": parts[1],
                "message": parts[2],
            })
    return changesets


def run(args: argparse.Namespace) -> int:
    """Execute changeset command."""
    changesets = _get_recent_commits(args.root, args.limit)

    result: dict[str, object] = {
        "command": "changeset",
        "root": args.root,
        "count": len(changesets),
        "changesets": changesets,
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Changesets (last {args.limit})")
        print(f"  Root:  {args.root}")
        print(f"  Found: {len(changesets)}")
        for cs in changesets:
            print(f"  {cs['sha']} | {cs['date']} | {cs['message'][:60]}")
        if not changesets:
            print("  (no changesets found)")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
