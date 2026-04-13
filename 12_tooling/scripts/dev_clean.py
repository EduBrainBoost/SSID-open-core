#!/usr/bin/env python3
"""AGENT 04 — Developer-safe cleanup script.

Removes Python-only noise artifacts from the repo tree:
  - __pycache__/ directories
  - .pytest_cache/ directories
  - .mypy_cache/ directories
  - .ruff_cache/ directories
  - *.pyc / *.pyo files

Safety constraints:
  - Only removes known noise patterns (no root-level operations)
  - Skips .git, node_modules, .venv
  - Prints every deletion for auditability
  - Dry-run mode by default (pass --apply to actually delete)

SoT v4.1.0 | ROOT-24-LOCK | Classification: Tooling
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

NOISE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
NOISE_EXTENSIONS = {".pyc", ".pyo"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv"}

REPO_ROOT = Path(__file__).resolve().parents[2]


def clean_noise(root: Path, apply: bool = False) -> int:
    """Remove noise artifacts. Returns count of items removed/found."""
    count = 0

    # Collect noise directories first (removing them also removes contained files)
    dirs_to_remove: list[Path] = []
    files_to_remove: list[Path] = []

    for item in root.rglob("*"):
        if any(part in SKIP_DIRS for part in item.parts):
            continue

        if item.is_dir() and item.name in NOISE_DIRS:
            dirs_to_remove.append(item)
            count += 1

        if item.is_file() and item.suffix in NOISE_EXTENSIONS:
            # Only add if not already inside a noise dir we will remove
            if not any(item.is_relative_to(d) for d in dirs_to_remove):
                files_to_remove.append(item)
                count += 1

    mode = "REMOVING" if apply else "WOULD REMOVE (dry-run)"

    for d in sorted(dirs_to_remove):
        print(f"  {mode}: {d.relative_to(root)}/")
        if apply:
            shutil.rmtree(d, ignore_errors=True)

    for f in sorted(files_to_remove):
        print(f"  {mode}: {f.relative_to(root)}")
        if apply:
            f.unlink(missing_ok=True)

    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean Python noise artifacts")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete files (default is dry-run)",
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=str(REPO_ROOT),
        help="Repository root path",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    if not (root / "16_codex").is_dir():
        print("DEV_CLEAN_FAIL: Cannot locate repo root", file=sys.stderr)
        return 1

    print(f"DEV_CLEAN: Scanning {root} ...")
    count = clean_noise(root, apply=args.apply)

    if count == 0:
        print("DEV_CLEAN_PASS: No noise artifacts found")
    elif args.apply:
        print(f"DEV_CLEAN_DONE: Removed {count} artifact(s)")
    else:
        print(f"DEV_CLEAN_DRY_RUN: Found {count} artifact(s) — pass --apply to delete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
