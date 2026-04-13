#!/usr/bin/env python3
"""Evidence Chain CLI v2 — scan, backfill (PR-only), and gate for SSID audit compliance.

Usage:
  python 12_tooling/cli/evidence_chain.py scan [--pr-only] [--limit N]
  python 12_tooling/cli/evidence_chain.py backfill-merges [--write]
  python 12_tooling/cli/evidence_chain.py scan --last-merge --require-agent-run --require-report-event
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

sys.path.insert(0, str(REPO_ROOT / "12_tooling" / "ops" / "evidence_chain"))
import evidence_chain_lib as ecl


def cmd_scan(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    if args.last_merge:
        commits = ecl.git_first_parent_commits(repo, limit=1)
        if not commits:
            print("FAIL: no commits found")
            return 1
        sha = commits[0]["merge_sha"]
        existing_runs = ecl.find_existing_agent_runs(repo)
        existing_events = ecl.find_existing_report_bus_shas(repo)
        has_run = sha in existing_runs or sha[:7] in existing_runs
        has_event = sha in existing_events or sha[:7] in existing_events
        fail = False
        if args.require_agent_run and not has_run:
            print(f"FAIL: merge {sha[:7]} missing agent_run")
            fail = True
        if args.require_report_event and not has_event:
            print(f"FAIL: merge {sha[:7]} missing report_bus event")
            fail = True
        if fail:
            return 1
        print(f"PASS: merge {sha[:7]} has required evidence")
        return 0
    result = ecl.scan(repo, limit=args.limit, pr_only=args.pr_only)
    print(
        json.dumps(
            {
                "total_commits": result["total_commits"],
                "commits_with_agent_run": result["commits_with_agent_run"],
                "commits_with_report_event": result["commits_with_report_event"],
                "missing_agent_runs": result["missing_agent_runs"],
                "missing_report_events": result["missing_report_events"],
            },
            indent=2,
        )
    )
    if result["missing_agent_runs"] > 0 or result["missing_report_events"] > 0:
        print(f"\nGaps: {result['missing_agent_runs']} missing runs, {result['missing_report_events']} missing events")
        return 1
    print("\nPASS: all PR merges have evidence coverage")
    return 0


def cmd_backfill_merges(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    print("Scanning PR merges...")
    scan_result = ecl.scan(repo, limit=args.limit, pr_only=True)
    print(f"PR merges found: {scan_result['total_commits']}")
    print(f"Missing agent_runs: {scan_result['missing_agent_runs']}")
    print(f"Missing report_events: {scan_result['missing_report_events']}")
    if scan_result["missing_agent_runs"] == 0 and scan_result["missing_report_events"] == 0:
        print("PASS: nothing to backfill")
        return 0
    backfill_result = ecl.backfill_pr_merges(repo, scan_result, write=args.write)
    if args.write:
        index = ecl.build_execution_index(repo, scan_result)
        idx_path = ecl.write_execution_index(repo, index)
        print(f"Wrote execution index: {idx_path}")
        gap_path = ecl.write_gap_report(repo, backfill_result)
        print(f"Wrote gap report: {gap_path}")
        sys.path.insert(0, str(REPO_ROOT / "12_tooling" / "cli"))
        import report_bus as rb_mod

        rb_mod.rebuild_jsonl()
        print("Rebuilt report_bus.jsonl from events/")
    print(f"\nAgent runs created: {len(backfill_result['created_agent_runs'])}")
    print(f"Events created: {len(backfill_result['created_events'])}")
    print(f"Unresolved gaps: {len(backfill_result['unresolved_gaps'])}")
    if not args.write:
        print("\nDry run (pass --write to apply)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence Chain CLI v2")
    parser.add_argument("--repo", default=str(REPO_ROOT))
    sub = parser.add_subparsers(dest="command")
    scan_p = sub.add_parser("scan", help="Scan for evidence gaps")
    scan_p.add_argument("--limit", type=int, default=200)
    scan_p.add_argument("--pr-only", action="store_true", help="Only include commits with PR numbers")
    scan_p.add_argument("--last-merge", action="store_true", help="Gate mode: check only last merge")
    scan_p.add_argument("--require-agent-run", action="store_true")
    scan_p.add_argument("--require-report-event", action="store_true")
    bf_p = sub.add_parser("backfill-merges", help="Backfill PR merges only")
    bf_p.add_argument("--write", action="store_true")
    bf_p.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "backfill-merges":
        return cmd_backfill_merges(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
