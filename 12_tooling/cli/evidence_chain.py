#!/usr/bin/env python3
"""Evidence Chain CLI v3 — status, backfill, scan, and gate for SSID audit compliance.

Usage:
  python 12_tooling/cli/evidence_chain.py status
  python 12_tooling/cli/evidence_chain.py backfill [--dry-run|--apply] [--limit N]
  python 12_tooling/cli/evidence_chain.py scan [--pr-only] [--limit N]
  python 12_tooling/cli/evidence_chain.py backfill-merges [--write]
  python 12_tooling/cli/evidence_chain.py scan --last-merge --require-agent-run --require-report-event
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

EVIDENCE_DIR = REPO_ROOT / ".ssid-system" / "evidence" / "10_repo_ssid"
AGENT_RUNS_DIR = REPO_ROOT / "02_audit_logging" / "agent_runs"
EXECUTION_INDEX = REPO_ROOT / "24_meta_orchestration" / "registry" / "execution_index.jsonl"

sys.path.insert(0, str(REPO_ROOT / "12_tooling" / "ops" / "evidence_chain"))
try:
    import evidence_chain_lib as ecl
except ImportError:
    ecl = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# status subcommand
# ---------------------------------------------------------------------------


def _collect_evidence_entries(repo: Path) -> list[dict[str, Any]]:
    """Collect all evidence entries from .ssid-system/evidence and agent_runs."""
    entries: list[dict[str, Any]] = []
    evidence_dir = repo / ".ssid-system" / "evidence"
    if evidence_dir.is_dir():
        for f in sorted(evidence_dir.rglob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    entries.append({"file": str(f.relative_to(repo)), "data": data})
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            entries.append({"file": str(f.relative_to(repo)), "data": item})
            except (json.JSONDecodeError, OSError):
                continue
    agent_runs = repo / "02_audit_logging" / "agent_runs"
    if agent_runs.is_dir():
        for d in sorted(agent_runs.iterdir()):
            if d.is_dir() and d.name.startswith("run-merge-"):
                sha = d.name.replace("run-merge-", "")
                meta = d / "meta.json"
                if meta.exists():
                    try:
                        data = json.loads(meta.read_text(encoding="utf-8"))
                        entries.append({"file": str(d.relative_to(repo)), "data": data, "commit_sha": sha})
                    except (json.JSONDecodeError, OSError):
                        entries.append({"file": str(d.relative_to(repo)), "data": {}, "commit_sha": sha})
                else:
                    entries.append({"file": str(d.relative_to(repo)), "data": {}, "commit_sha": sha})
    return entries


def _compute_chain_hash(entries: list[dict[str, Any]]) -> str:
    """Compute a rolling SHA256 over all evidence entries for chain integrity."""
    h = hashlib.sha256()
    for e in entries:
        h.update(json.dumps(e.get("data", {}), sort_keys=True, default=str).encode())
    return h.hexdigest()


def cmd_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    entries = _collect_evidence_entries(repo)
    chain_hash = _compute_chain_hash(entries)
    last_entry = entries[-1] if entries else None
    print(
        json.dumps(
            {
                "total_entries": len(entries),
                "last_entry": last_entry.get("file") if last_entry else None,
                "chain_hash": chain_hash,
                "chain_valid": len(entries) > 0,
            },
            indent=2,
        )
    )
    return 0


# ---------------------------------------------------------------------------
# backfill subcommand
# ---------------------------------------------------------------------------


def _get_merge_commits(repo: Path, limit: int = 200) -> list[dict[str, str]]:
    """Get merge commits from git log."""
    try:
        raw = subprocess.check_output(
            ["git", "log", "--first-parent", f"-n{limit}", "--merges", "--pretty=format:%H|%cI|%s"],
            cwd=str(repo),
            text=True,
            errors="replace",
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    if not raw:
        return []
    results = []
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        sha, date_str, subject = parts
        results.append({"sha": sha, "date": date_str, "subject": subject})
    return results


def _existing_evidence_shas(repo: Path) -> set[str]:
    """Collect all commit SHAs that already have evidence entries."""
    shas: set[str] = set()
    agent_runs = repo / "02_audit_logging" / "agent_runs"
    if agent_runs.is_dir():
        for d in agent_runs.iterdir():
            if d.is_dir() and d.name.startswith("run-merge-"):
                shas.add(d.name.replace("run-merge-", ""))
    # Also check execution_index.jsonl
    idx = repo / "24_meta_orchestration" / "registry" / "execution_index.jsonl"
    if idx.exists():
        try:
            for line in idx.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if "commit_sha" in entry:
                    shas.add(entry["commit_sha"])
                    shas.add(entry["commit_sha"][:7])
        except (json.JSONDecodeError, OSError):
            pass
    return shas


def _create_backfill_entry(repo: Path, commit: dict[str, str], apply: bool) -> dict[str, Any]:
    """Create a retroactive evidence entry for a merge commit."""
    sha = commit["sha"]
    short_sha = sha[:7]
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "timestamp": now,
        "agent_id": "evidence_chain_cli",
        "operation": "backfill",
        "commit_sha": sha,
        "commit_sha_short": short_sha,
        "commit_date": commit["date"],
        "commit_subject": commit["subject"],
        "provenance": "DERIVED_GIT",
        "backfill_generated": True,
    }
    if apply:
        # Write agent_run directory
        run_dir = repo / "02_audit_logging" / "agent_runs" / f"run-merge-{short_sha}"
        run_dir.mkdir(parents=True, exist_ok=True)
        meta = run_dir / "meta.json"
        meta.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
        # Append to execution_index.jsonl
        idx = repo / "24_meta_orchestration" / "registry" / "execution_index.jsonl"
        idx.parent.mkdir(parents=True, exist_ok=True)
        with open(idx, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def cmd_backfill(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    apply = args.apply
    limit = args.limit
    merges = _get_merge_commits(repo, limit=limit)
    existing = _existing_evidence_shas(repo)
    missing = []
    for m in merges:
        sha = m["sha"]
        short = sha[:7]
        if sha not in existing and short not in existing:
            missing.append(m)
    print(f"Merge commits scanned: {len(merges)}")
    print(f"Already covered: {len(merges) - len(missing)}")
    print(f"Missing evidence: {len(missing)}")
    if not missing:
        print("Nothing to backfill.")
        return 0
    created = []
    for m in missing:
        entry = _create_backfill_entry(repo, m, apply=apply)
        created.append(entry)
        mode = "APPLIED" if apply else "DRY-RUN"
        print(f"  [{mode}] {m['sha'][:7]} — {m['subject'][:60]}")
    print(f"\nEntries {'created' if apply else 'would create'}: {len(created)}")
    if not apply:
        print("(pass --apply to write)")
    return 0


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
    parser = argparse.ArgumentParser(description="Evidence Chain CLI v3")
    parser.add_argument("--repo", default=str(REPO_ROOT))
    sub = parser.add_subparsers(dest="command")

    # --- status ---
    sub.add_parser("status", help="Show evidence chain integrity status")

    # --- backfill (new: --dry-run / --apply) ---
    bf2_p = sub.add_parser("backfill", help="Backfill merge commits without evidence")
    bf2_g = bf2_p.add_mutually_exclusive_group()
    bf2_g.add_argument("--dry-run", dest="apply", action="store_false", default=False, help="Preview only (default)")
    bf2_g.add_argument("--apply", dest="apply", action="store_true", help="Write entries")
    bf2_p.add_argument("--limit", type=int, default=200)

    # --- scan (legacy v2) ---
    scan_p = sub.add_parser("scan", help="Scan for evidence gaps")
    scan_p.add_argument("--limit", type=int, default=200)
    scan_p.add_argument("--pr-only", action="store_true", help="Only include commits with PR numbers")
    scan_p.add_argument("--last-merge", action="store_true", help="Gate mode: check only last merge")
    scan_p.add_argument("--require-agent-run", action="store_true")
    scan_p.add_argument("--require-report-event", action="store_true")

    # --- backfill-merges (legacy v2) ---
    bf_p = sub.add_parser("backfill-merges", help="Backfill PR merges only (legacy)")
    bf_p.add_argument("--write", action="store_true")
    bf_p.add_argument("--limit", type=int, default=200)

    args = parser.parse_args()
    if args.command == "status":
        return cmd_status(args)
    elif args.command == "backfill":
        return cmd_backfill(args)
    elif args.command == "scan":
        return cmd_scan(args)
    elif args.command == "backfill-merges":
        return cmd_backfill_merges(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
