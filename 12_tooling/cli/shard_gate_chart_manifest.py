#!/usr/bin/env python3
"""Gate: chart.yaml + manifest.yaml presence check per shard.
Exit 0 = PASS, Exit 1 = FAIL.

Usage:
    shard_gate_chart_manifest.py                     # check ALL roots x ALL shards
    shard_gate_chart_manifest.py --root 03_core      # check one root, all 16 shards
    shard_gate_chart_manifest.py --root 03_core --pilot  # legacy: only shards 01+02
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Kept for backward-compat with --pilot flag; no longer used as default scope.
PILOT_SHARDS = [
    "01_identitaet_personen",
    "02_dokumente_nachweise",
]


def check_shard(shard_dir: Path) -> dict:
    """Check chart.yaml and manifest.yaml presence for a shard."""
    has_chart = (shard_dir / "chart.yaml").exists()
    has_manifest = (shard_dir / "manifest.yaml").exists()
    return {"shard": shard_dir.name, "chart": has_chart, "manifest": has_manifest}


def discover_roots() -> list[Path]:
    """Return all top-level root directories that contain a shards/ subdirectory."""
    return sorted(
        d for d in PROJECT_ROOT.iterdir()
        if d.is_dir() and (d / "shards").is_dir()
    )


def run_root(root_dir: Path, pilot: bool) -> tuple[list[dict], list[str]]:
    """Run gate checks for one root directory. Returns (results, failures)."""
    shards_dir = root_dir / "shards"
    root_name = root_dir.name

    if pilot:
        shard_dirs = [shards_dir / s for s in PILOT_SHARDS if (shards_dir / s).is_dir()]
    else:
        shard_dirs = sorted(d for d in shards_dir.iterdir() if d.is_dir())

    results = []
    failures = []
    for shard_dir in shard_dirs:
        r = check_shard(shard_dir)
        issues = []
        if not r["chart"]:
            issues.append("missing chart.yaml")
        if not r["manifest"]:
            issues.append("missing manifest.yaml")

        label = f"{root_name}/shards/{r['shard']}"
        if issues:
            failures.append(label)
            print(f"FAIL: {label} -- {', '.join(issues)}")
        else:
            print(f"PASS: {label}")
        results.append({"root": root_name, **r})

    return results, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate: chart+manifest presence")
    parser.add_argument(
        "--root",
        default=None,
        help="Root dirname (e.g. 03_core). Omit to check ALL roots.",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Legacy: only check pilot shards (01, 02). Ignored when --root is omitted.",
    )
    parser.add_argument("--report", type=str, help="Write JSON report to path")
    args = parser.parse_args()

    if args.root:
        root_dir = PROJECT_ROOT / args.root
        if not (root_dir / "shards").is_dir():
            print(f"ERROR: Shards directory not found: {root_dir / 'shards'}")
            return 1
        roots = [root_dir]
    else:
        roots = discover_roots()
        if not roots:
            print("ERROR: No root directories with shards/ found.")
            return 1
        print(f"INFO: Discovered {len(roots)} roots with shards/")

    all_results: list[dict] = []
    all_failures: list[str] = []

    for root_dir in roots:
        results, failures = run_root(root_dir, pilot=args.pilot and args.root is not None)
        all_results.extend(results)
        all_failures.extend(failures)

    verdict = "FAIL" if all_failures else "PASS"
    roots_label = args.root if args.root else f"{len(roots)} roots"
    print(
        f"\n{verdict}: {len(all_results)} shards checked across {roots_label}, "
        f"{len(all_failures)} failures"
    )

    if args.report:
        report = {
            "gate": "shard_gate_chart_manifest",
            "root": args.root or "ALL",
            "pilot": args.pilot and args.root is not None,
            "verdict": verdict,
            "violations": all_failures,
            "checked": [
                f"{r['root']}/shards/{r['shard']}" for r in all_results
            ],
        }
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"REPORT: {args.report}")

    return 1 if all_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
