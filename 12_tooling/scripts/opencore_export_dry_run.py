#!/usr/bin/env python3
"""OpenCore Export Dry-Run -- simulates export without pushing.

Checks the full allowlist, denylist, and forbidden extensions pipeline
and produces a JSON manifest of what WOULD be exported.

This is a lightweight wrapper around export_opencore_filtered.py --dry-run
with additional forbidden-extension checking and human-readable summary.

Exit codes:
  0 -- dry-run passed, export would succeed
  1 -- dry-run found issues (forbidden files would leak)
  2 -- configuration error
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_POLICY = "16_codex/opencore_export_policy.yaml"
DEFAULT_ALLOWLIST = "23_compliance/policies/open_core_export_allowlist.yaml"

FORBIDDEN_EXTENSIONS = {
    ".pem", ".key", ".p12", ".jks", ".pfx",
    ".env", ".secret", ".secrets", ".token",
    ".pyc", ".pyo",
}

EXIT_PASS = 0
EXIT_ISSUES = 1
EXIT_CONFIG_ERROR = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo: Path, args: list[str]) -> str:
    cmd = ["git", "-C", str(repo), *args]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout


def git_ls_tree(repo: Path, ref: str) -> list[str]:
    raw = git(repo, ["ls-tree", "-r", "--name-only", ref])
    return [p.strip() for p in raw.splitlines() if p.strip()]


def load_yaml_safe(path: Path) -> dict[str, Any]:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        data: dict[str, Any] = {}
        current_key: str | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- "):
                if current_key:
                    data.setdefault(current_key, []).append(
                        stripped[2:].strip().strip("\"'")
                    )
            elif ":" in stripped:
                key = stripped.split(":")[0].strip()
                val = stripped.split(":", 1)[1].strip()
                current_key = key
                if val and not val.startswith("|") and not val.startswith(">"):
                    data[key] = val.strip("\"'")
        return data


def is_denied_by_glob(path_posix: str, deny_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_posix, g) for g in deny_globs)


def is_in_deny_roots(path_posix: str, deny_roots: list[str]) -> bool:
    for root in deny_roots:
        root_prefix = root.rstrip("/") + "/"
        if path_posix.startswith(root_prefix) or path_posix == root.rstrip("/"):
            return True
    return False


def is_in_allow_prefixes(path_posix: str, allow_prefixes: list[str]) -> bool:
    for prefix in allow_prefixes:
        if prefix.endswith("/"):
            if path_posix.startswith(prefix):
                return True
        else:
            if path_posix == prefix:
                return True
    return False


def has_forbidden_extension(path_posix: str) -> bool:
    name = path_posix.rsplit("/", 1)[-1] if "/" in path_posix else path_posix
    for ext in FORBIDDEN_EXTENSIONS:
        if name.endswith(ext) or name == ext.lstrip("."):
            return True
    return False


# ---------------------------------------------------------------------------
# Dry-run logic
# ---------------------------------------------------------------------------
def run_dry_export(
    repo_root: Path,
    policy_path: Path,
    allowlist_path: Path | None,
    commit_ref: str = "HEAD",
) -> dict[str, Any]:
    policy = load_yaml_safe(policy_path)
    deny_globs = policy.get("deny_globs", []) or []
    deny_roots = policy.get("deny_roots", []) or []
    allow_prefixes = policy.get("allow_prefixes", []) or []

    allowlist: dict[str, Any] = {}
    denied_patterns: list[str] = []
    if allowlist_path and allowlist_path.exists():
        allowlist = load_yaml_safe(allowlist_path)
        denied_patterns = allowlist.get("denied_patterns", []) or []

    source_commit = git(repo_root, ["rev-parse", commit_ref]).strip()
    all_files = git_ls_tree(repo_root, commit_ref)

    included: list[str] = []
    excluded_not_allowed: list[str] = []
    excluded_deny_glob: list[str] = []
    excluded_deny_root: list[str] = []
    forbidden_ext_hits: list[str] = []

    # Determine allowed root files from allowlist
    root_files = set(allowlist.get("root_files", []) or [])
    allowed_paths = allowlist.get("allowed_paths", []) or []

    for f in all_files:
        # Check deny roots first
        if is_in_deny_roots(f, deny_roots):
            excluded_deny_root.append(f)
            continue

        # Check deny globs
        if is_denied_by_glob(f, deny_globs):
            excluded_deny_glob.append(f)
            continue

        # Check allowlist
        is_allowed = False
        if "/" not in f and f in root_files:
            is_allowed = True
        elif allow_prefixes and is_in_allow_prefixes(f, allow_prefixes):
            is_allowed = True
        elif allowed_paths:
            for prefix in allowed_paths:
                prefix_clean = prefix.rstrip("/") + "/"
                if f.startswith(prefix_clean):
                    is_allowed = True
                    break

        if not is_allowed:
            excluded_not_allowed.append(f)
            continue

        # Check denied patterns from allowlist
        basename = f.rsplit("/", 1)[-1] if "/" in f else f
        pattern_denied = False
        for pattern in denied_patterns:
            if pattern.endswith("/"):
                if f"/{pattern}" in f"/{f}/" or f.startswith(pattern):
                    pattern_denied = True
                    break
            elif fnmatch.fnmatch(basename, pattern):
                pattern_denied = True
                break

        if pattern_denied:
            excluded_deny_glob.append(f)
            continue

        included.append(f)

    # Check forbidden extensions on included files
    for f in included:
        if has_forbidden_extension(f):
            forbidden_ext_hits.append(f)

    has_issues = bool(forbidden_ext_hits)

    report = {
        "generated_utc": utc_now(),
        "tool": "opencore_export_dry_run",
        "version": "1.0.0",
        "status": "ISSUES_FOUND" if has_issues else "PASS",
        "exit_code": EXIT_ISSUES if has_issues else EXIT_PASS,
        "source_commit": source_commit,
        "policy_file": str(policy_path.relative_to(repo_root)),
        "policy_sha256": sha256_file(policy_path),
        "allowlist_file": str(allowlist_path.relative_to(repo_root)) if allowlist_path else "",
        "allowlist_sha256": sha256_file(allowlist_path) if allowlist_path and allowlist_path.exists() else "",
        "counts": {
            "total_tracked": len(all_files),
            "included": len(included),
            "excluded_deny_root": len(excluded_deny_root),
            "excluded_deny_glob": len(excluded_deny_glob),
            "excluded_not_allowed": len(excluded_not_allowed),
            "forbidden_extension_hits": len(forbidden_ext_hits),
        },
        "included_files": sorted(included),
        "excluded_files": {
            "deny_root": sorted(excluded_deny_root)[:50],
            "deny_glob": sorted(excluded_deny_glob)[:50],
            "not_allowed": sorted(excluded_not_allowed)[:50],
        },
        "forbidden_extension_hits": sorted(forbidden_ext_hits),
    }
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="opencore_export_dry_run",
        description="Simulate open-core export and report included/excluded files.",
    )
    p.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="SSID repo root",
    )
    p.add_argument("--commit", default="HEAD", help="Source commit ref")
    p.add_argument("--policy", default=DEFAULT_POLICY, help="Export policy YAML")
    p.add_argument("--allowlist", default=DEFAULT_ALLOWLIST, help="Allowlist YAML")
    p.add_argument("--output-file", default=None, help="Write report to file")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo_root / policy_path
    if not policy_path.exists():
        print(f"ERROR: policy not found: {policy_path}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    allowlist_path = Path(args.allowlist)
    if not allowlist_path.is_absolute():
        allowlist_path = repo_root / allowlist_path
    if not allowlist_path.exists():
        allowlist_path = None

    try:
        report = run_dry_export(
            repo_root=repo_root,
            policy_path=policy_path,
            allowlist_path=allowlist_path,
            commit_ref=args.commit,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"

    if args.output_file:
        Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_file).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output_file}")
    else:
        print(output)

    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
