#!/usr/bin/env python3
"""Orchestrator Pre-Run Truth Gate — fail-closed (v2).

Mandatory preflight before ANY orchestrator swarm or PR action.
Establishes live-repo truth from git + GitHub API only.
Plan-state is never authoritative. Only git fetch + gh pr view is truth.

Exit 0 = CLEAN — swarm may proceed.
Exit 1 = VIOLATIONS — swarm BLOCKED, no task may start.

Usage:
    # Basic (current repo + EduBrainBoost/SSID-EMS):
    python orchestrator_truth_gate.py

    # With explicit repo→local-path mapping (enables worktree checks per repo):
    python orchestrator_truth_gate.py \\
        --repo-paths "EduBrainBoost/SSID:${REPO_ROOT}/SSID" \\
                     "EduBrainBoost/SSID-EMS:${REPO_ROOT}/SSID-EMS"

    # Check planned PR numbers are not already MERGED/CLOSED:
    python orchestrator_truth_gate.py --planned-prs "EduBrainBoost/SSID:110,111" "EduBrainBoost/SSID-EMS:192"

    # Machine-readable JSON snapshot:
    python orchestrator_truth_gate.py --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _lib.canonical_paths import ensure_canonical_repo_root

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPOS = ["EduBrainBoost/SSID", "EduBrainBoost/SSID-EMS"]

# Untracked files matching these patterns are policy violations (FAIL, not warn)
FAIL_UNTRACKED_PATTERNS = [
    ".tmp_evidence",
    ".env",
    "*.secret",
    "*.key",
]
# These are accepted as non-blocking untracked noise
ACCEPTED_UNTRACKED_PREFIXES = (
    "tasks/",
    ".ssid-system/",
    ".pytest_cache/",
    "__pycache__/",
    ".ruff_cache/",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], *, cwd: Path, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), check=check)


def _gh_json(args: list[str], *, cwd: Path = REPO_ROOT) -> Any:
    """Call gh with JSON output. Returns parsed object or None on failure."""
    r = _run(["gh"] + args, cwd=cwd)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _classify_untracked(files: list[str]) -> tuple[list[str], list[str]]:
    """Split untracked files into (fail_list, warn_list)."""
    fail_list, warn_list = [], []
    for f in files:
        is_accepted = any(f.startswith(p) for p in ACCEPTED_UNTRACKED_PREFIXES)
        if is_accepted:
            continue
        is_policy_violation = any(
            (pat.startswith("*") and f.endswith(pat[1:])) or pat in f for pat in FAIL_UNTRACKED_PATTERNS
        )
        if is_policy_violation:
            fail_list.append(f)
        else:
            warn_list.append(f)
    return fail_list, warn_list


# ---------------------------------------------------------------------------
# Truth Gate
# ---------------------------------------------------------------------------


@dataclass
class TruthGateResult:
    passed: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)

    def fail(self, msg: str) -> None:
        self.passed = False
        self.violations.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _check_worktree(result: TruthGateResult, repo: str, local_path: Path) -> dict:
    """Worktree dirty/ahead checks for a specific local repo path."""
    info: dict[str, Any] = {"repo": repo, "local_path": str(local_path)}

    if not local_path.exists():
        result.warn(f"{repo}: local path {local_path} not found — skipping worktree check")
        return info

    try:
        local_path = ensure_canonical_repo_root(
            local_path,
            expected_repo_name=repo.split("/")[-1],
            repo_root=REPO_ROOT,
        )
        info["local_path"] = str(local_path)
    except ValueError as exc:
        result.fail(f"{repo}: non-canonical repo path rejected: {exc}")
        return info

    # Step 1: fetch
    r = _run(["git", "fetch", "--all", "--prune"], cwd=local_path)
    if r.returncode != 0:
        result.fail(f"{repo}: git fetch failed: {r.stderr.strip()[:120]}")
        return info

    # Step 2: origin/main SHA
    r = _run(["git", "rev-parse", "origin/main"], cwd=local_path)
    if r.returncode != 0:
        result.fail(f"{repo}: cannot resolve origin/main")
        return info
    info["origin_main_sha"] = r.stdout.strip()

    # Step 5a: unstaged / staged
    r_unstaged = _run(["git", "diff", "--ignore-submodules=dirty", "--name-only"], cwd=local_path)
    r_staged = _run(["git", "diff", "--cached", "--ignore-submodules=dirty", "--name-only"], cwd=local_path)
    unstaged = [l for l in r_unstaged.stdout.splitlines() if l.strip()]
    staged = [l for l in r_staged.stdout.splitlines() if l.strip()]
    info["unstaged"] = unstaged
    info["staged"] = staged

    if unstaged or staged:
        result.fail(
            f"{repo}: worktree dirty — {len(unstaged)} unstaged, {len(staged)} staged. Commit or stash before swarm."
        )

    # Step 5b: local HEAD ahead of origin/main
    r_head = _run(["git", "rev-parse", "HEAD"], cwd=local_path)
    local_sha = r_head.stdout.strip()
    info["local_head_sha"] = local_sha

    r_ahead = _run(["git", "diff", "--name-only", "origin/main...HEAD"], cwd=local_path)
    ahead_files = [l for l in r_ahead.stdout.splitlines() if l.strip()]
    info["local_ahead_files"] = ahead_files

    if ahead_files:
        result.fail(f"{repo}: local HEAD ahead of origin/main by {len(ahead_files)} file(s). Push before swarm.")

    # Step 9: untracked classification
    r_status = _run(["git", "ls-files", "--others", "--exclude-standard"], cwd=local_path)
    untracked_raw = [l.strip() for l in r_status.stdout.splitlines() if l.strip()]
    fail_untracked, warn_untracked = _classify_untracked(untracked_raw)
    info["untracked_fail"] = fail_untracked
    info["untracked_warn"] = warn_untracked

    for f in fail_untracked:
        result.fail(f"{repo}: policy-violating untracked artifact: {f}")

    if warn_untracked:
        # Non-policy untracked files: warn only (runtime noise, reports, etc.)
        result.warn(f"{repo}: {len(warn_untracked)} untracked file(s) (non-blocking): {warn_untracked[:3]}")

    return info


def _check_open_prs(result: TruthGateResult, repos: list[str]) -> list[dict]:
    """Step 3+4+6+7: Live PR enumeration and overlap check per repo."""
    all_prs: list[dict] = []

    for repo in repos:
        r = _run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--repo",
                repo,
                "--json",
                "number,title,headRefName,mergeable,baseRefName,mergeStateStatus",
            ],
            cwd=REPO_ROOT,
        )
        if r.returncode != 0:
            result.warn(f"Cannot list open PRs for {repo}: {r.stderr.strip()[:80]}")
            continue

        try:
            prs = json.loads(r.stdout)
        except json.JSONDecodeError:
            prs = []

        for pr in prs:
            nr = pr["number"]
            head_ref = pr.get("headRefName", "")
            merge_state = pr.get("mergeStateStatus", "UNKNOWN")
            mergeable = pr.get("mergeable", "UNKNOWN")

            # Step 6: enrich with files
            pr_view = (
                _gh_json(
                    ["pr", "view", str(nr), "--repo", repo, "--json", "files,state,mergeStateStatus"],
                    cwd=REPO_ROOT,
                )
                or {}
            )
            pr_files = {f["path"] for f in pr_view.get("files", [])}

            # Step 7: file overlap vs origin/main (gh-only, works cross-repo)
            overlap_warning = _detect_overlap(repo, nr, pr_files, head_ref)
            if overlap_warning:
                result.warn(overlap_warning)

            if merge_state == "BLOCKED":
                result.warn(f"PR #{nr} ({repo}) mergeStateStatus=BLOCKED — resolve conflicts before swarm.")

            all_prs.append(
                {
                    "repo": repo,
                    "number": nr,
                    "title": pr.get("title", ""),
                    "headRefName": head_ref,
                    "mergeable": mergeable,
                    "mergeStateStatus": merge_state,
                    "files_count": len(pr_files),
                    "files_sample": sorted(pr_files)[:5],
                }
            )

    return all_prs


def _detect_overlap(repo: str, pr_nr: int, pr_files: set[str], head_ref: str) -> str | None:
    """Step 7: Check if PR files were already merged into origin/main of that repo.
    Uses gh api to get recent main commits — works for any repo regardless of local worktree.
    """
    if not pr_files:
        return None

    # Get recent commits on main for that repo (last 20)
    r = _run(
        ["gh", "api", f"repos/{repo}/commits", "--jq", ".[].files[].filename", "-f", "per_page=20"],
        cwd=REPO_ROOT,
    )
    # Note: /commits endpoint doesn't include files; use compare instead
    # Use compare between PR head and main to find overlap
    r = _run(
        ["gh", "api", f"repos/{repo}/compare/{head_ref}...main", "--jq", ".files[].filename"],
        cwd=REPO_ROOT,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None

    main_changed = set(r.stdout.splitlines())
    overlap = pr_files & main_changed
    if not overlap:
        return None

    return (
        f"PR #{pr_nr} ({repo}): {len(overlap)} file(s) already changed in main since branch: "
        f"{sorted(overlap)[:3]} — verify PR is not superseded."
    )


def _check_planned_prs(result: TruthGateResult, planned: dict[str, list[int]]) -> list[dict]:
    """Step 8: For each planned PR, fetch live state. FAIL if already MERGED or CLOSED."""
    checked: list[dict] = []

    for repo, numbers in planned.items():
        for nr in numbers:
            r = _run(
                ["gh", "pr", "view", str(nr), "--repo", repo, "--json", "state,title,mergedAt,closedAt,headRefName"],
                cwd=REPO_ROOT,
            )
            if r.returncode != 0:
                result.fail(f"Planned PR #{nr} ({repo}): cannot fetch live state — {r.stderr.strip()[:80]}")
                continue

            try:
                info = json.loads(r.stdout)
            except json.JSONDecodeError:
                result.fail(f"Planned PR #{nr} ({repo}): malformed JSON response")
                continue

            state = info.get("state", "UNKNOWN")
            title = info.get("title", "")
            if state in ("MERGED", "CLOSED"):
                result.fail(
                    f"Planned PR #{nr} ({repo}) is already {state} "
                    f"('{title[:50]}'). Remove from task list before swarm."
                )

            checked.append(
                {
                    "repo": repo,
                    "number": nr,
                    "title": title,
                    "state": state,
                    "headRefName": info.get("headRefName", ""),
                }
            )

    return checked


def run_truth_gate(
    repos: list[str],
    repo_paths: dict[str, Path],
    planned_prs: dict[str, list[int]],
) -> TruthGateResult:
    result = TruthGateResult()
    snapshot: dict[str, Any] = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "worktree_checks": {},
        "open_prs": [],
        "planned_pr_checks": [],
    }

    # --- Worktree checks (per repo with known local path) ---
    for repo, local_path in repo_paths.items():
        wt = _check_worktree(result, repo, local_path)
        snapshot["worktree_checks"][repo] = wt
        if "origin_main_sha" in wt:
            snapshot[f"origin_main_{repo.split('/')[-1]}"] = wt["origin_main_sha"]

    # --- Open PR checks ---
    open_prs = _check_open_prs(result, repos)
    snapshot["open_prs"] = open_prs
    snapshot["open_pr_count"] = len(open_prs)

    # --- Planned PR checks (Step 8) ---
    if planned_prs:
        planned_checks = _check_planned_prs(result, planned_prs)
        snapshot["planned_pr_checks"] = planned_checks

    snapshot["pass"] = result.passed
    snapshot["violation_count"] = len(result.violations)
    snapshot["warning_count"] = len(result.warnings)
    result.snapshot = snapshot
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_repo_paths(raw: list[str]) -> dict[str, Path]:
    """Parse 'EduBrainBoost/SSID:/path/to/repo' entries."""
    out: dict[str, Path] = {}
    for item in raw:
        if ":" not in item:
            continue
        # Handle Windows paths like C:/foo → split on first colon only for repo part
        parts = item.split(":", 1)
        repo = parts[0].strip()
        path_str = parts[1].strip()
        # Re-attach drive letter if next char is /
        # e.g. "EduBrainBoost/SSID" + "C:/Users/..." — already correct after split(1)
        out[repo] = Path(path_str)
    return out


def _parse_planned_prs(raw: list[str]) -> dict[str, list[int]]:
    """Parse 'EduBrainBoost/SSID:110,111' entries."""
    out: dict[str, list[int]] = {}
    for item in raw:
        if ":" not in item:
            continue
        repo, numbers_str = item.split(":", 1)
        repo = repo.strip()
        numbers = [int(n.strip()) for n in numbers_str.split(",") if n.strip().isdigit()]
        if numbers:
            out[repo] = numbers
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orchestrator Pre-Run Truth Gate v2 — fail-closed")
    parser.add_argument("--repos", nargs="*", default=DEFAULT_REPOS, help="GitHub repos to check for open PRs")
    parser.add_argument(
        "--repo-paths",
        nargs="*",
        default=[],
        metavar="REPO:PATH",
        help="Local worktree paths per repo, e.g. EduBrainBoost/SSID:/path/to/ssid",
    )
    parser.add_argument(
        "--planned-prs",
        nargs="*",
        default=[],
        metavar="REPO:NR,NR",
        help="Planned PR numbers to verify are not already merged, e.g. EduBrainBoost/SSID:110,111",
    )
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output machine-readable JSON snapshot")
    args = parser.parse_args(argv)

    # Defaults: if no --repo-paths given, use REPO_ROOT for the first repo
    repo_paths = _parse_repo_paths(args.repo_paths)
    if not repo_paths and args.repos:
        repo_paths[args.repos[0]] = REPO_ROOT

    planned_prs = _parse_planned_prs(args.planned_prs)
    result = run_truth_gate(args.repos, repo_paths, planned_prs)
    snap = result.snapshot

    if args.json_output:
        print(json.dumps(snap, indent=2))
        return 0 if result.passed else 1

    # Human-readable
    status_line = "TRUTH GATE: PASS" if result.passed else "TRUTH GATE: FAIL"
    sep = "=" * 64
    print(f"\n{sep}")
    print(f"  {status_line}")
    for repo, wt in snap.get("worktree_checks", {}).items():
        sha = wt.get("origin_main_sha", "?")[:12]
        print(f"  {repo.split('/')[-1]} origin/main: {sha}")
    print(f"  open PRs:   {snap.get('open_pr_count', 0)}")
    print(f"  violations: {len(result.violations)}")
    print(f"  warnings:   {len(result.warnings)}")
    print(sep)

    if result.violations:
        print("\n[VIOLATIONS — SWARM BLOCKED]")
        for v in result.violations:
            print(f"  FAIL: {v}")

    if result.warnings:
        print("\n[WARNINGS]")
        for w in result.warnings:
            print(f"  WARN: {w}")

    if not result.violations:
        if result.warnings:
            print("\n  No violations. Swarm may proceed (warnings noted).")
        else:
            print("\n  All checks clean. Swarm may proceed.")

    if snap.get("open_prs"):
        print("\n[OPEN PRs]")
        for pr in snap["open_prs"]:
            print(
                f"  #{pr['number']} [{pr.get('mergeStateStatus', '?')}] "
                f"{pr['repo'].split('/')[-1]} — {pr['title'][:55]}"
            )

    if snap.get("planned_pr_checks"):
        print("\n[PLANNED PR LIVE STATE]")
        for pr in snap["planned_pr_checks"]:
            print(f"  #{pr['number']} {pr['state']} — {pr['title'][:55]}")

    print()
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
