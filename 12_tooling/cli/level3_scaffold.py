#!/usr/bin/env python3
"""
Level-3 Root Scaffold Generator — applies L3 templates to all 24 roots.
Idempotent, no-overwrite. Default: dry-run. Use --apply to persist.

Templates: 16_codex/templates/level3_root_scaffold/
Report:    02_audit_logging/reports/LEVEL3_SCAFFOLD_APPLY.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.shards import ROOTS_24

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO_ROOT / "16_codex" / "templates" / "level3_root_scaffold"
REPORT_PATH = REPO_ROOT / "02_audit_logging" / "reports" / "LEVEL3_SCAFFOLD_APPLY.json"

# Files that must exist in every root (relative to root dir)
REQUIRED_FILES: list[dict] = [
    {
        "path": "tests/test_root_smoke.py",
        "template": "test_root_smoke.py.tpl",
        "variable": "ROOT_NAME",
    },
    {
        "path": "docs/ARCHITECTURE.md",
        "template": "ARCHITECTURE.md.tpl",
        "variable": "ROOT_NAME",
    },
]


def render_template(template_path: Path, root_name: str) -> str:
    """Render a template by replacing ${ROOT_NAME} with the actual root name."""
    content = template_path.read_text(encoding="utf-8")
    return content.replace("${ROOT_NAME}", root_name)


def process_root(root_name: str, apply: bool) -> dict:
    """Check and optionally scaffold a single root. Returns per-root result."""
    root_dir = REPO_ROOT / root_name
    result = {"root": root_name, "created": [], "skipped": [], "errors": []}

    if not root_dir.is_dir():
        result["errors"].append(f"Root directory missing: {root_name}")
        return result

    for spec in REQUIRED_FILES:
        target = root_dir / spec["path"]
        template = TEMPLATE_DIR / spec["template"]

        if target.exists():
            result["skipped"].append(spec["path"])
            print(f"SKIP (exists): {root_name}/{spec['path']}")
            continue

        if not template.exists():
            result["errors"].append(f"Template missing: {spec['template']}")
            print(f"ERROR: Template missing: {spec['template']}")
            continue

        rendered = render_template(template, root_name)

        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            result["created"].append(spec["path"])
            print(f"CREATED: {root_name}/{spec['path']}")
        else:
            result["created"].append(spec["path"])
            print(f"WOULD CREATE: {root_name}/{spec['path']}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Level-3 Root Scaffold Generator (idempotent, no-overwrite)"
    )
    parser.add_argument(
        "--root", type=str, help="Process single root (e.g. 03_core)"
    )
    parser.add_argument(
        "--all", action="store_true", dest="all_roots", help="Process all 24 roots"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Write scaffold files (default: dry-run)"
    )
    parser.add_argument(
        "--report", type=str, help="Write JSON report to path (default: canonical path)"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check mode: FAIL (exit 1) if any root is missing scaffold files"
    )
    args = parser.parse_args()

    if not args.root and not args.all_roots:
        print("ERROR: Specify --root <name> or --all")
        return 2

    if args.root and args.root not in ROOTS_24:
        print(f"ERROR: Unknown root '{args.root}'. Valid: {', '.join(ROOTS_24)}")
        return 2

    roots = ROOTS_24 if args.all_roots else [args.root]

    mode = "CHECK" if args.check else ("APPLY" if args.apply else "DRY-RUN")
    print(f"INFO: Mode={mode}, Roots={len(roots)}")

    all_results = []
    for root_name in roots:
        result = process_root(root_name, args.apply and not args.check)
        all_results.append(result)

    total_created = sum(len(r["created"]) for r in all_results)
    total_skipped = sum(len(r["skipped"]) for r in all_results)
    total_errors = sum(len(r["errors"]) for r in all_results)

    print(f"\nSummary: {total_created} created, {total_skipped} skipped, {total_errors} errors")

    # Write report
    report_path = Path(args.report) if args.report else REPORT_PATH
    report = {
        "mode": mode,
        "roots_processed": len(roots),
        "total_created": total_created,
        "total_skipped": total_skipped,
        "total_errors": total_errors,
        "results": all_results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Report written to: {report_path}")

    if args.check and total_created > 0:
        print(f"FAIL: {total_created} scaffold file(s) missing across roots")
        return 1

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
