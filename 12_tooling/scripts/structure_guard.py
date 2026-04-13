#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

EXIT_CODE = 24

def die(msg: str) -> None:
    print(f"STRUCTURE_GUARD_FAIL: {msg}")
    raise SystemExit(EXIT_CODE)

def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    exc_file = repo_root / "23_compliance" / "exceptions" / "root_level_exceptions.yaml"
    if not exc_file.exists():
        die(f"missing exceptions file: {exc_file.as_posix()}")

    data = yaml.safe_load(exc_file.read_text(encoding="utf-8")) or {}
    allowed_dirs = set(data.get("allowed_directories", []) or [])
    allowed_files = set(data.get("allowed_files", []) or [])

    roots = sorted([p.name for p in repo_root.iterdir() if p.is_dir() and p.name[:2].isdigit() and "_" in p.name])
    if len(roots) != 24:
        die(f"expected 24 root modules, found {len(roots)}: {roots}")

    # Forbidden archive extensions at repo root (deny even if allowlisted)
    forbidden_archive_exts = {".zip", ".tgz", ".7z"}

    for p in repo_root.iterdir():
        name = p.name
        if p.is_symlink():
            die(f"symlink forbidden: {name}")

        if p.is_dir() and name[:2].isdigit() and "_" in name:
            continue

        # In a git worktree, ".git" is a file (not a directory) containing
        # a gitdir pointer.  Allow it at the repo root without failing.
        if name == ".git" and p.is_file():
            log.info("STRUCTURE_GUARD_INFO: .git is a file (git worktree marker) — allowed")
            continue

        # Archive check runs before allowlist (archives never allowed at root)
        if p.is_file():
            if p.suffix.lower() in forbidden_archive_exts:
                die(f"forbidden archive in root: {name}")
            if name.lower().endswith(".tar.gz"):
                die(f"forbidden archive in root: {name}")

        if p.is_dir():
            if name not in allowed_dirs:
                die(f"unauthorized root directory: {name}")
        else:
            if name not in allowed_files:
                die(f"unauthorized root file: {name}")

    print("STRUCTURE_GUARD_PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
