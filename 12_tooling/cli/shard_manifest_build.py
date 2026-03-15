#!/usr/bin/env python3
"""
Shard Manifest Builder — scans chart.yaml files, generates missing shard-level manifest.yaml.
Default: dry-run (no --apply = read-only). Use --apply to persist.
`--refresh-existing` updates manifest content in place for already present manifests.

Output: <root>/shards/<shard>/manifest.yaml (next to chart.yaml)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

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
    return sorted(
        p.relative_to(shard_dir).as_posix()
        for p in contracts_dir.glob("*.schema.json")
    )


def discover_conformance(shard_dir: Path) -> list[str]:
    """Find conformance fixture paths relative to shard dir."""
    conf_dir = shard_dir / "conformance" / "fixtures"
    if not conf_dir.is_dir():
        return []
    return sorted(
        p.relative_to(shard_dir).as_posix()
        for p in conf_dir.glob("*.json")
    )


def discover_runtime(shard_dir: Path) -> list[str]:
    runtime_dir = shard_dir / "runtime"
    if not runtime_dir.is_dir():
        return []
    return sorted(
        p.relative_to(shard_dir).as_posix()
        for p in runtime_dir.glob("*.yaml")
    )


def discover_runtime_dependencies(shard_dir: Path) -> list[str]:
    runtime_index = shard_dir / "runtime" / "index.yaml"
    if not runtime_index.is_file():
        return []
    runtime_spec = yaml.safe_load(runtime_index.read_text(encoding="utf-8")) or {}
    return list(runtime_spec.get("dependency_refs", []) or [])


def derive_policies(chart: dict) -> list[dict]:
    """Extract policy refs from chart.yaml policies list."""
    policies = chart.get("policies", [])
    return [{"ref": p["id"]} for p in policies if isinstance(p, dict) and "id" in p]


def generate_manifest(shard_dir: Path, root_name: str, chart: dict) -> dict:
    """Generate manifest.yaml content from chart.yaml + filesystem."""
    contracts = discover_contracts(shard_dir)
    conformance = discover_conformance(shard_dir)
    runtime = discover_runtime(shard_dir)
    dependencies = discover_runtime_dependencies(shard_dir)
    return {
        "shard_id": shard_dir.name,
        "root_id": root_name,
        "version": chart.get("version", "0.1.0"),
        "status": chart.get("status", "defined"),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "implementation_stack": "generated",
        "contracts": contracts,
        "conformance": conformance,
        "runtime": runtime,
        "dependencies": dependencies,
        "policies": derive_policies(chart),
        "evidence_outputs": [
            {
                "path": f"{root_name}/shards/{shard_dir.name}/evidence",
                "strategy": chart.get("evidence_strategy", {}).get("mode", "hash_manifest_only"),
            }
        ],
    }


def write_yaml_force(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    content = content.replace("\r\n", "\n")
    path.write_bytes(content.encode("utf-8"))


def process_root(root_path: Path, apply: bool, refresh_existing: bool) -> dict:
    """Process all shards in a root. Returns {created: [], skipped: [], errors: []}."""
    result = {"created": [], "updated": [], "skipped": [], "errors": []}
    root_name = root_path.name
    shards = find_shards(root_path)

    for shard_dir in shards:
        chart_path = shard_dir / "chart.yaml"
        manifest_path = shard_dir / "manifest.yaml"

        if not chart_path.exists():
            result["errors"].append(f"{shard_dir.name}: missing chart.yaml")
            continue

        chart = parse_yaml(chart_path)
        if chart is None:
            result["errors"].append(f"{shard_dir.name}: chart.yaml not parseable")
            continue

        manifest = generate_manifest(shard_dir, root_name, chart)

        if manifest_path.exists() and not refresh_existing:
            result["skipped"].append(shard_dir.name)
            print(f"SKIP (exists): {root_name}/shards/{shard_dir.name}/manifest.yaml")
            continue

        if apply:
            if manifest_path.exists() and refresh_existing:
                write_yaml_force(manifest_path, manifest)
                result["updated"].append(shard_dir.name)
                print(f"UPDATED: {root_name}/shards/{shard_dir.name}/manifest.yaml")
            elif write_yaml(manifest_path, manifest):
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
    parser = argparse.ArgumentParser(
        description="Shard Manifest Builder (parametric, additiv-only, no-overwrite)"
    )
    parser.add_argument("--root", type=str, help="Process single root (e.g. 03_core)")
    parser.add_argument("--all", action="store_true", dest="all_roots", help="Process all 24 roots")
    parser.add_argument("--apply", action="store_true", help="Write manifests (default: dry-run)")
    parser.add_argument("--refresh-existing", action="store_true", help="Rewrite existing manifest.yaml files from current chart + filesystem state")
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
        result = process_root(root_path, args.apply, args.refresh_existing)
        all_results[root_path.name] = result

    # Summary
    total_created = sum(len(r["created"]) for r in all_results.values())
    total_updated = sum(len(r["updated"]) for r in all_results.values())
    total_skipped = sum(len(r["skipped"]) for r in all_results.values())
    total_errors = sum(len(r["errors"]) for r in all_results.values())
    print(f"\nSummary: {total_created} created, {total_updated} updated, {total_skipped} skipped, {total_errors} errors")

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
