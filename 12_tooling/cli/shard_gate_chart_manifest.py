#!/usr/bin/env python3
"""Gate: chart.yaml + manifest.yaml presence check per shard.
Exit 0 = PASS, Exit 1 = FAIL.

Usage:
    shard_gate_chart_manifest.py --root 03_core --pilot
    shard_gate_chart_manifest.py --root 03_core
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PILOT_SHARDS = [
    "01_identitaet_personen",
    "02_dokumente_nachweise",
]


def check_shard(shard_dir: Path) -> dict:
    """Check chart.yaml and manifest.yaml presence for a shard."""
    has_chart = (shard_dir / "chart.yaml").exists()
    has_manifest = (shard_dir / "manifest.yaml").exists()
    return {"shard": shard_dir.name, "chart": has_chart, "manifest": has_manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate: chart+manifest presence")
    parser.add_argument("--root", required=True, help="Root dirname (e.g. 03_core)")
    parser.add_argument("--pilot", action="store_true", help="Only check pilot shards (01, 02)")
    parser.add_argument("--report", type=str, help="Write JSON report to path")
    args = parser.parse_args()

    shards_dir = PROJECT_ROOT / args.root / "shards"
    if not shards_dir.is_dir():
        print(f"ERROR: Shards directory not found: {shards_dir}")
        return 1

    if args.pilot:
        shard_dirs = [shards_dir / s for s in PILOT_SHARDS if (shards_dir / s).is_dir()]
    else:
        shard_dirs = sorted(d for d in shards_dir.iterdir() if d.is_dir())

    results = [check_shard(d) for d in shard_dirs]
    failures = []
    checked = []

    for r in results:
        checked.append(f"{args.root}/shards/{r['shard']}")
        issues = []
        if not r["chart"]:
            issues.append("missing chart.yaml")
        if not r["manifest"]:
            issues.append("missing manifest.yaml")

        if issues:
            failures.append(r["shard"])
            print(f"FAIL: {r['shard']} -- {', '.join(issues)}")
        else:
            print(f"PASS: {r['shard']}")

    verdict = "FAIL" if failures else "PASS"
    print(f"\n{verdict}: {len(results)} shards checked, {len(failures)} failures")

    if args.report:
        report = {
            "gate": "shard_gate_chart_manifest",
            "root": args.root,
            "pilot": args.pilot,
            "verdict": verdict,
            "violations": [f"{s}: missing chart.yaml or manifest.yaml" for s in failures],
            "checked": checked,
        }
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"REPORT: {args.report}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
