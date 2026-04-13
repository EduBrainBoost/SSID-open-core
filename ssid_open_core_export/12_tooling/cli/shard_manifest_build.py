#!/usr/bin/env python3
"""
Shard Manifest Builder — scans chart.yaml files, generates missing shard-level manifest.yaml.
Additiv-only: never overwrites existing manifests. Duplicate guard.
Default: dry-run (no --apply = read-only). Use --apply to persist.

Output: <root>/shards/<shard>/manifest.yaml (next to chart.yaml)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.shards import (
    ROOTS_24,
    find_roots,
    find_shards,
    parse_yaml,
    write_yaml,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def discover_contracts(shard_dir: Path) -> list[str]:
    """Find contract schema paths relative to shard dir."""
    contracts_dir = shard_dir / "contracts"
    if not contracts_dir.is_dir():
        return []
    return sorted(p.relative_to(shard_dir).as_posix() for p in contracts_dir.glob("*.schema.json"))


def discover_conformance(shard_dir: Path) -> list[str]:
    """Find conformance fixture paths relative to shard dir."""
    conf_dir = shard_dir / "conformance" / "fixtures"
    if not conf_dir.is_dir():
        return []
    return sorted(p.relative_to(shard_dir).as_posix() for p in conf_dir.glob("*.json"))


def derive_policies(chart: dict) -> list[dict]:
    """Extract policy refs from chart.yaml policies list."""
    policies = chart.get("policies", [])
    return [{"ref": p["id"]} for p in policies if isinstance(p, dict) and "id" in p]


def generate_manifest(shard_dir: Path, root_name: str, chart: dict) -> dict:
    """Generate manifest.yaml content from chart.yaml + filesystem."""
    return {
        "shard_id": shard_dir.name,
        "root_id": root_name,
        "version": chart.get("version", "0.1.0"),
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "implementation_stack": "generated",
        "contracts": discover_contracts(shard_dir),
        "conformance": discover_conformance(shard_dir),
        "policies": derive_policies(chart),
    }


def process_root(root_path: Path, apply: bool) -> dict:
    """Process all shards in a root. Returns {created: [], skipped: [], errors: []}."""
    result = {"created": [], "skipped": [], "errors": []}
    root_name = root_path.name
    shards = find_shards(root_path)

    for shard_dir in shards:
        chart_path = shard_dir / "chart.yaml"
        manifest_path = shard_dir / "manifest.yaml"

        if not chart_path.exists():
            result["errors"].append(f"{shard_dir.name}: missing chart.yaml")
            continue

        if manifest_path.exists():
            result["skipped"].append(shard_dir.name)
            print(f"SKIP (exists): {root_name}/shards/{shard_dir.name}/manifest.yaml")
            continue

        chart = parse_yaml(chart_path)
        if chart is None:
            result["errors"].append(f"{shard_dir.name}: chart.yaml not parseable")
            continue

        manifest = generate_manifest(shard_dir, root_name, chart)

        if apply:
            if write_yaml(manifest_path, manifest):
                result["created"].append(shard_dir.name)
                print(f"CREATED: {root_name}/shards/{shard_dir.name}/manifest.yaml")
            else:
                result["skipped"].append(shard_dir.name)
                print(f"SKIP (duplicate guard): {root_name}/shards/{shard_dir.name}/manifest.yaml")
        else:
            result["created"].append(shard_dir.name)
            print(f"WOULD CREATE: {root_name}/shards/{shard_dir.name}/manifest.yaml")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Shard Manifest Builder (parametric, additiv-only, no-overwrite)")
    parser.add_argument("--root", type=str, help="Process single root (e.g. 03_core)")
    parser.add_argument("--all", action="store_true", dest="all_roots", help="Process all 24 roots")
    parser.add_argument("--apply", action="store_true", help="Write manifests (default: dry-run)")
    parser.add_argument("--report", type=str, help="Write JSON report to path")
    args = parser.parse_args()

    # Validation
    if args.apply and not args.root and not args.all_roots:
        print("ERROR: --apply requires --root <name> or --all")
        return 2

    if args.root and args.root not in ROOTS_24:
        print(f"ERROR: Unknown root '{args.root}'. Valid: {', '.join(ROOTS_24)}")
        return 2

    if not args.root and not args.all_roots:
        print("INFO: No --root or --all specified. Use --root <name> or --all to scan.")
        print(f"INFO: Available roots ({len(ROOTS_24)}): {', '.join(ROOTS_24)}")
        return 0

    # Determine roots to process
    if args.all_roots:
        roots = find_roots(REPO_ROOT)
    else:
        root_path = REPO_ROOT / args.root
        if not root_path.is_dir():
            print(f"ERROR: Root directory not found: {root_path}")
            return 2
        roots = [root_path]

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"INFO: Mode={mode}, Roots={len(roots)}")

    all_results = {}
    for root_path in roots:
        result = process_root(root_path, args.apply)
        all_results[root_path.name] = result

    # Summary
    total_created = sum(len(r["created"]) for r in all_results.values())
    total_skipped = sum(len(r["skipped"]) for r in all_results.values())
    total_errors = sum(len(r["errors"]) for r in all_results.values())
    print(f"\nSummary: {total_created} created, {total_skipped} skipped, {total_errors} errors")

    # Report
    if args.report:
        Path(args.report).write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report written to: {args.report}")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
