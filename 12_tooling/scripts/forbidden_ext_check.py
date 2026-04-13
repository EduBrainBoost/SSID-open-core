#!/usr/bin/env python3
"""
AR-07: Forbidden Extensions Check
SoT-Regel: master_v1.1.1 §6 (.ipynb .parquet .sqlite .db)
Vollständig deterministisch — kein Claude-Agent.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", ".pytest_cache", "__pycache__"}

def sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""

def check(repo_root: Path, extensions: set, changed_files=None, scan_all=False) -> dict:
    violations = []
    total_checked = 0

    if scan_all:
        candidates = [p for p in repo_root.rglob("*") if p.is_file()]
    elif changed_files:
        candidates = [repo_root / f for f in changed_files if (repo_root / f).is_file()]
    else:
        candidates = []

    for p in candidates:
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        total_checked += 1
        ext = p.suffix.lower()
        if ext in extensions:
            violations.append({
                "file": str(p.relative_to(repo_root)),
                "ext": ext,
                "sha256": sha256(p),
                "sot_rule": "master_v1.1.1_§6",
            })

    return {
        "violations": violations,
        "total_checked": total_checked,
        "total_violations": len(violations),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extensions", required=True,
                        help="Space-separated list, e.g. '.ipynb .parquet .sqlite .db'")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--changed-files", default="",
                        help="Newline or space-separated file list")
    parser.add_argument("--scan-all", default="false")
    args = parser.parse_args()

    exts = set(args.extensions.split())
    root = Path(args.repo_root).resolve()
    changed = [f for f in args.changed_files.split() if f] if args.changed_files else []
    do_scan_all = args.scan_all.lower() == "true"

    result = check(root, exts, changed_files=changed, scan_all=do_scan_all)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["total_violations"] > 0 else 0)
