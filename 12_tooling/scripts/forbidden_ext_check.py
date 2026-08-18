#!/usr/bin/env python3
"""Check for forbidden file extensions in the repository."""

import argparse
import json
import sys
from pathlib import Path


EXCLUDE_DIRS = [
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".ssid-system",
]


def should_skip(path: Path) -> bool:
    """Check if path should be skipped."""
    path_str = str(path).lower()
    for exclude in EXCLUDE_DIRS:
        if exclude in path_str:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Check for forbidden file extensions")
    parser.add_argument("--repo-root", required=True, help="Repository root path")
    parser.add_argument("--extensions", required=True, help="Space-separated extensions to check")
    parser.add_argument("--scan-all", default="false", help="Scan all files")

    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    forbidden_exts = args.extensions.split()
    violations = []

    # Scan all files in repo
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue

        if should_skip(file_path):
            continue

        # Check if file has forbidden extension
        for ext in forbidden_exts:
            if file_path.name.endswith(ext):
                violations.append({
                    "file": str(file_path),
                    "ext": ext,
                    "sot_rule": "master_v1.1.1_§6",
                })
                break

    # Output JSON
    result = {
        "total_violations": len(violations),
        "violations": violations,
    }

    print(json.dumps(result))

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
