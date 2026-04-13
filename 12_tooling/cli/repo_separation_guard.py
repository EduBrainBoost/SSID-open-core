#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import yaml


FORBIDDEN_GLOBS: Sequence[str] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.jks",
    "*.pfx",
    "*.secrets",
    "*.secret",
    "*.token",
)

FORBIDDEN_PATH_PREFIXES: Sequence[str] = (
    ".ssid_sandbox/",
    "02_audit_logging/agent_runs/",
    "02_audit_logging/raw_logs/",
)

# Paths matching these prefixes are exempt from FORBIDDEN_PATH_PREFIXES
# (e.g., backfill evidence derived from git history)
ALLOWED_EXCEPTIONS: Sequence[str] = (
    "02_audit_logging/agent_runs/run-merge-",
    "02_audit_logging/agent_runs/backfill/",
)

PLAN_SCHEMA = "24_meta_orchestration/plans/TASK_SPEC_MINIMAL.schema.yaml"
PLANS_DIR = "24_meta_orchestration/plans"
ADR_DIR = "16_codex/decisions"

ADR_TRIGGER_PREFIXES: Sequence[str] = (
    ".github/workflows/",
    "16_codex/governance/",
    "16_codex/agents/",
    "24_meta_orchestration/",
)


def _run_git(root: Path, args: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _is_git_worktree(root: Path) -> bool:
    proc = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"


def _tracked_files(root: Path) -> List[str]:
    proc = _run_git(root, ["ls-files"])
    if proc.returncode != 0:
        return []
    return [ln.strip().replace("\\", "/") for ln in proc.stdout.splitlines() if ln.strip()]


def _has_forbidden_path(path: str) -> bool:
    norm = path.replace("\\", "/")
    if any(norm.startswith(ex) for ex in ALLOWED_EXCEPTIONS):
        return False
    return any(norm.startswith(prefix) for prefix in FORBIDDEN_PATH_PREFIXES)


def _matches_forbidden_glob(path: str) -> bool:
    norm = path.replace("\\", "/")
    name = Path(norm).name
    # Allow .env.example (safe template files)
    if name == ".env.example":
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(norm, pattern) for pattern in FORBIDDEN_GLOBS)


def _iter_tree_files(root: Path) -> Iterable[str]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(".git/"):
            continue
        yield rel


def _iter_forbidden_glob_matches(root: Path, paths: Iterable[str]) -> Iterable[str]:
    path_set = set(paths)
    for pattern in FORBIDDEN_GLOBS:
        for p in root.glob(pattern):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                # Skip .env.example files (safe templates)
                if rel == ".env.example" or rel.endswith("/.env.example"):
                    continue
                if rel in path_set:
                    yield rel


def _validate_plan_specs(root: Path) -> List[str]:
    problems: List[str] = []
    schema_path = root / PLAN_SCHEMA
    plans_dir = root / PLANS_DIR

    if not schema_path.exists():
        return [f"missing schema file: {schema_path.as_posix()}"]
    if not plans_dir.exists():
        return [f"missing plans directory: {plans_dir.as_posix()}"]

    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    required = set(schema.get("required", []))

    plan_files = sorted(
        [p for p in plans_dir.glob("*.yaml")
         if p.name != Path(PLAN_SCHEMA).name
         and not p.name.startswith("PLANSPEC_")],
        key=lambda p: p.name,
    )
    if not plan_files:
        problems.append("no plan specs found in 24_meta_orchestration/plans/")
        return problems

    for plan in plan_files:
        data = yaml.safe_load(plan.read_text(encoding="utf-8")) or {}
        missing = sorted(required - set(data.keys()))
        if missing:
            problems.append(f"{plan.as_posix()}: missing required fields {missing}")
            continue

        checks = data.get("acceptance_checks", [])
        if checks != ["policy", "sot", "qa"]:
            problems.append(f"{plan.as_posix()}: acceptance_checks must be exactly [policy, sot, qa]")

        if not isinstance(data.get("do_not_touch"), list) or not data.get("do_not_touch"):
            problems.append(f"{plan.as_posix()}: do_not_touch must be a non-empty list")

        sc = data.get("stop_conditions", {})
        if not isinstance(sc, dict) or "fail_after" not in sc or "on_missing_paths" not in sc:
            problems.append(f"{plan.as_posix()}: stop_conditions requires fail_after and on_missing_paths")

    return problems


def _changed_files_for_adr(root: Path) -> Tuple[Optional[List[str]], Optional[str]]:
    if not _is_git_worktree(root):
        patch_files = _changed_files_from_patch(root)
        if patch_files is not None:
            return patch_files, None
        return None, "ADR diff unavailable (no git worktree and no patch.diff)"

    ranges: List[str] = []
    base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    if base_ref:
        ranges.append(f"origin/{base_ref}...HEAD")
        ranges.append(f"{base_ref}...HEAD")
        ranges.append("HEAD~1...HEAD")
    else:
        # No PR context (workflow_dispatch, push): use merge-base against origin/main
        mb = _run_git(root, ["merge-base", "HEAD", "origin/main"])
        if mb.returncode == 0 and mb.stdout.strip():
            ranges.append(f"{mb.stdout.strip()}...HEAD")
        ranges.append("HEAD~1...HEAD")

    last_error = ""
    for range_spec in ranges:
        diff = _run_git(root, ["diff", "--name-only", range_spec])
        if diff.returncode == 0:
            files = [ln.strip().replace("\\", "/") for ln in diff.stdout.splitlines() if ln.strip()]
            return files, None
        stderr = (diff.stderr or "").strip()
        last_error = f"git diff failed for range '{range_spec}': {stderr or 'unknown error'}"

    # deterministic fallback: use patch files when available
    patch_files = _changed_files_from_patch(root)
    if patch_files is not None:
        return patch_files, None
    return None, last_error or "unable to determine changed files for ADR check"


def _changed_files_from_patch(root: Path) -> Optional[List[str]]:
    candidates: List[Path] = []
    direct = root / "patch.diff"
    if direct.exists():
        candidates.append(direct)
    candidates.extend(sorted(root.glob("02_audit_logging/agent_runs/*/patch.diff"), key=lambda p: p.stat().st_mtime, reverse=True))
    if not candidates:
        return None

    patch = candidates[0]
    changed: List[str] = []
    for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("+++ b/"):
            rel = line[6:].strip()
        elif line.startswith("--- a/"):
            rel = line[6:].strip()
        else:
            continue
        if rel and rel != "/dev/null" and rel not in changed:
            changed.append(rel)
    return changed


def _adr_required(changed_files: List[str]) -> bool:
    return any(any(p.startswith(prefix) for prefix in ADR_TRIGGER_PREFIXES) for p in changed_files)


def _adr_present_in_change(changed_files: List[str]) -> bool:
    return any(p.startswith("16_codex/decisions/ADR_") and p.endswith(".md") for p in changed_files)


def _audit_path_violations(paths: Iterable[str]) -> List[str]:
    violations: List[str] = []
    for rel in paths:
        norm = rel.replace("\\", "/")
        if _has_forbidden_path(norm):
            violations.append(norm)
        if norm.startswith("02_audit_logging/agent_runs/"):
            # Allow backfill/run-merge paths (any filenames)
            if any(norm.startswith(ex) for ex in ALLOWED_EXCEPTIONS):
                continue
            base = Path(norm).name
            if base not in {"manifest.json", "patch.diff", "patch.sha256"}:
                violations.append(norm)
    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser(description="Repo separation and governance guard")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    try:
        failures: List[str] = []

        if _is_git_worktree(root):
            scan_paths = _tracked_files(root)
            if not scan_paths:
                print("FAIL")
                print("TOOLING_ERROR: git ls-files returned empty set")
                return 3
        else:
            patch_paths = _changed_files_from_patch(root)
            if patch_paths is None:
                print("FAIL")
                print("TOOLING_ERROR: non-git mode requires patch.diff")
                return 3
            scan_paths = patch_paths

        for rel in scan_paths:
            if _has_forbidden_path(rel):
                failures.append(rel)
            if _matches_forbidden_glob(rel):
                failures.append(rel)
        for rel in sorted(set(_iter_forbidden_glob_matches(root, scan_paths))):
            failures.append(rel)
        failures.extend(_audit_path_violations(scan_paths))
        failures.extend(_validate_plan_specs(root))

        adr_root = root / ADR_DIR
        if not adr_root.exists():
            failures.append("16_codex/decisions/")
        else:
            adr_seed = adr_root / "ADR_0001_root24_lock_and_change_control.md"
            if not adr_seed.exists():
                failures.append("16_codex/decisions/ADR_0001_root24_lock_and_change_control.md")

        changed, changed_err = _changed_files_for_adr(root)
        if changed_err is not None:
            print("FAIL")
            print(f"TOOLING_ERROR: {changed_err}")
            return 3
        if changed is None:
            print("FAIL")
            print("TOOLING_ERROR: changed file set is undefined")
            return 3
        if _adr_required(changed) and not _adr_present_in_change(changed):
            failures.append("16_codex/decisions/ADR_*.md")

        if failures:
            print("FAIL")
            for item in sorted(set(failures)):
                print(item)
            return 2

        print("PASS")
        return 0
    except Exception as exc:  # deterministic tooling failure path
        print("FAIL")
        print(f"TOOLING_ERROR: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
