#!/usr/bin/env python3
"""ssidctl remediation -- List open remediation tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for remediation."""
    if subparsers is not None:
        parser = subparsers.add_parser("remediation", help="List open remediation tasks")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl remediation", description=__doc__)
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--status", choices=["open", "closed", "all"], default="open", help="Filter by status")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def _scan_remediation_markers(repo_root: Path) -> list[dict[str, str]]:
    """Scan for TODO/FIXME/REMEDIATION markers in Python files."""
    tasks: list[dict[str, str]] = []
    tooling_dir = repo_root / "12_tooling"
    if not tooling_dir.is_dir():
        return tasks
    for py_file in sorted(tooling_dir.rglob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            for marker in ("REMEDIATION:", "FIXME:", "TODO:"):
                if marker in line:
                    tasks.append(
                        {
                            "file": str(py_file.relative_to(repo_root)),
                            "line": str(i),
                            "marker": marker.rstrip(":"),
                            "text": line.strip()[:120],
                        }
                    )
    return tasks


def run(args: argparse.Namespace) -> int:
    """Execute remediation command."""
    repo_root = Path(args.root).resolve()
    tasks = _scan_remediation_markers(repo_root)

    result: dict[str, object] = {
        "command": "remediation",
        "root": str(repo_root),
        "filter": args.status,
        "tasks_found": len(tasks),
        "tasks": tasks[:50],
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Remediation Tasks (filter: {args.status})")
        print(f"  Root:  {repo_root}")
        print(f"  Found: {len(tasks)} marker(s)")
        for t in tasks[:20]:
            print(f"  [{t['marker']}] {t['file']}:{t['line']} -- {t['text'][:80]}")
        if len(tasks) > 20:
            print(f"  ... and {len(tasks) - 20} more")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
