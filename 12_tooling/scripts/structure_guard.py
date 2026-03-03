#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
import yaml

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

    for p in repo_root.iterdir():
        name = p.name
        if p.is_symlink():
            die(f"symlink forbidden: {name}")

        if p.is_dir() and name[:2].isdigit() and "_" in name:
            continue

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
