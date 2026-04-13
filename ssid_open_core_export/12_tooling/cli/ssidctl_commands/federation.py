#!/usr/bin/env python3
"""ssidctl federation -- Show federation status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for federation."""
    if subparsers is not None:
        parser = subparsers.add_parser("federation", help="Show federation status")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl federation", description=__doc__)
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def _scan_federation_config(repo_root: Path) -> dict[str, object]:
    """Scan for federation configuration artifacts."""
    interop_dir = repo_root / "10_interoperability"
    configs: list[str] = []
    if interop_dir.is_dir():
        for f in sorted(interop_dir.rglob("*federation*")):
            if ".git" not in f.parts:
                configs.append(str(f.relative_to(repo_root)))
    return {
        "interop_dir_exists": interop_dir.is_dir(),
        "federation_configs": configs,
        "config_count": len(configs),
    }


def run(args: argparse.Namespace) -> int:
    """Execute federation command."""
    repo_root = Path(args.root).resolve()
    scan = _scan_federation_config(repo_root)

    result: dict[str, object] = {
        "command": "federation",
        "root": str(repo_root),
        "status": "configured" if scan["config_count"] else "unconfigured",
        **scan,
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print("Federation Status")
        print(f"  Root:          {repo_root}")
        print(f"  Interop Dir:   {'found' if scan['interop_dir_exists'] else 'MISSING'}")
        print(f"  Configs Found: {scan['config_count']}")
        print(f"  Status:        {result['status']}")
        if args.verbose and scan["federation_configs"]:
            for c in scan["federation_configs"]:  # type: ignore[union-attr]
                print(f"    - {c}")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
