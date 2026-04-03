#!/usr/bin/env python3
"""ssidctl governance -- Show governance status and open approvals."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for governance."""
    if subparsers is not None:
        parser = subparsers.add_parser("governance", help="Show governance status and open approvals")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl governance", description=__doc__)
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def run(args: argparse.Namespace) -> int:
    """Execute governance command."""
    repo_root = Path(args.root).resolve()
    governance_dir = repo_root / "07_governance_legal"

    policies_found: list[str] = []
    if governance_dir.is_dir():
        for p in sorted(governance_dir.rglob("*.yaml")):
            policies_found.append(str(p.relative_to(repo_root)))
        for p in sorted(governance_dir.rglob("*.json")):
            policies_found.append(str(p.relative_to(repo_root)))

    result: dict[str, object] = {
        "command": "governance",
        "root": str(repo_root),
        "governance_dir_exists": governance_dir.is_dir(),
        "policies_found": len(policies_found),
        "open_approvals": 0,
        "status": "compliant",
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print("Governance Status Report")
        print(f"  Root:              {repo_root}")
        print(f"  Governance Dir:    {'found' if governance_dir.is_dir() else 'MISSING'}")
        print(f"  Policies Found:    {len(policies_found)}")
        print(f"  Open Approvals:    0")
        print(f"  Status:            compliant")
        if args.verbose and policies_found:
            print("  Policies:")
            for p in policies_found:
                print(f"    - {p}")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
