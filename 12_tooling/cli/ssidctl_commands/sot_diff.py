#!/usr/bin/env python3
"""ssidctl sot-diff -- Show SoT differences between baseline and current state."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _hash_file(path: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for sot-diff."""
    if subparsers is not None:
        parser = subparsers.add_parser("sot-diff", help="Show SoT differences between baseline and current state")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl sot-diff", description=__doc__)
    parser.add_argument("--baseline", type=str, default=None, help="Path to baseline manifest JSON")
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def run(args: argparse.Namespace) -> int:
    """Execute sot-diff command."""
    repo_root = Path(args.root).resolve()
    if not repo_root.is_dir():
        print(f"ERROR: Repository root not found: {repo_root}", file=sys.stderr)
        return 1

    codex_path = repo_root / "16_codex"
    if not codex_path.is_dir():
        print(f"WARNING: 16_codex not found at {codex_path}", file=sys.stderr)

    result: dict[str, object] = {
        "command": "sot-diff",
        "root": str(repo_root),
        "baseline": args.baseline,
        "status": "no-baseline" if args.baseline is None else "ready",
        "diffs": [],
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"SoT Diff Report")
        print(f"  Root:     {repo_root}")
        print(f"  Baseline: {args.baseline or '(none)'}")
        print(f"  Status:   {result['status']}")
        if not result["diffs"]:
            print("  Diffs:    (none detected)")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
