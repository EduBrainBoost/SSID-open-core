#!/usr/bin/env python3
"""ssidctl promote -- Initiate promotion workflow (dry-run by default)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for promote."""
    if subparsers is not None:
        parser = subparsers.add_parser("promote", help="Initiate promotion workflow (dry-run default)")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl promote", description=__doc__)
    parser.add_argument("--target", type=str, required=False, help="Promotion target (e.g. staging, production)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry-run mode (default: enabled)")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run", help="Disable dry-run, execute for real")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def run(args: argparse.Namespace) -> int:
    """Execute promote command."""
    timestamp = datetime.now(UTC).isoformat()
    result: dict[str, object] = {
        "command": "promote",
        "target": args.target or "(unspecified)",
        "dry_run": args.dry_run,
        "timestamp": timestamp,
        "status": "dry-run-complete" if args.dry_run else "blocked-no-approval",
    }

    if not args.dry_run and args.target is None:
        print("ERROR: --target is required when not in dry-run mode", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        mode = "DRY-RUN" if args.dry_run else "LIVE"
        print(f"Promotion Workflow [{mode}]")
        print(f"  Target:    {result['target']}")
        print(f"  Timestamp: {timestamp}")
        print(f"  Status:    {result['status']}")
        if args.dry_run:
            print("  (No changes applied -- dry-run mode)")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
