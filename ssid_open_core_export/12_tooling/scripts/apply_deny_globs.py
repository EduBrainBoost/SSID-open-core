#!/usr/bin/env python3
"""
AR-08: Filter files by deny_globs from opencore_export_policy.yaml
"""

import argparse
import fnmatch
import json
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}


def matches_any_glob(path_str: str, globs: list) -> bool:
    for g in globs:
        # Direct match
        if fnmatch.fnmatch(path_str, g):
            return True
        # Match against any suffix (for patterns like "dir/**")
        # Split path and try matching sub-paths
        parts = path_str.replace("\\", "/").split("/")
        for i in range(len(parts)):
            sub = "/".join(parts[i:])
            # Try the glob without leading wildcards
            g_clean = g.lstrip("*/")
            if g_clean and fnmatch.fnmatch(sub, g_clean):
                return True
            # Also try full sub-path against glob prefix
            # For "dir/**" patterns, check if path starts with "dir/"
            if g.endswith("/**"):
                prefix = g[:-3]
                if path_str.replace("\\", "/").startswith(prefix + "/"):
                    return True
    return False


def apply_deny_globs(repo_root: Path, deny_globs: list) -> dict:
    all_files = []
    denied_files = []
    sync_files = []

    for p in repo_root.rglob("*"):
        if p.is_dir():
            continue
        if any(s in p.parts for s in SKIP_DIRS):
            continue
        rel = str(p.relative_to(repo_root)).replace("\\", "/")
        all_files.append(rel)
        if matches_any_glob(rel, deny_globs):
            denied_files.append(rel)
        else:
            sync_files.append(rel)

    return {
        "total_files": len(all_files),
        "denied_files": denied_files,
        "files_to_sync": sync_files,
        "deny_globs_applied": deny_globs,
    }


if __name__ == "__main__":
    import yaml

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--policy", default="16_codex/opencore_export_policy.yaml")
    parser.add_argument("--deny-globs", default="", help="Space-separated list (overrides policy)")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()

    if args.deny_globs:
        deny_globs = args.deny_globs.split()
    else:
        policy_path = root / args.policy
        policy = yaml.safe_load(policy_path.read_text())
        deny_globs = policy["deny_globs"]

    result = apply_deny_globs(root, deny_globs)
    print(json.dumps(result, indent=2))
