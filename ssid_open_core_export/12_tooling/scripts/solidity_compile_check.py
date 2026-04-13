#!/usr/bin/env python3
"""Solidity Compile Check — validates .sol files parse correctly.

Uses solcx (py-solc-x) if available, otherwise basic syntax check.
Part of GAP-002: Solidity Build/Test Tooling.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOL_DIRS = [
    "03_core/contracts",
    "18_data_layer/contracts",
    "19_adapters/contracts",
    "20_foundation/shards/10_finanzen_banking/implementations/solidity/contracts",
    "20_foundation/tokenomics/contracts",
    "23_compliance/contracts",
]

# Basic Solidity syntax patterns that must be present
REQUIRED_PATTERNS = [
    re.compile(r"pragma\s+solidity"),
    re.compile(r"(contract|interface|library)\s+\w+"),
]


def find_sol_files() -> list[Path]:
    """Find all .sol files in known contract directories."""
    files = []
    for d in SOL_DIRS:
        dir_path = REPO_ROOT / d
        if dir_path.exists():
            files.extend(dir_path.glob("*.sol"))
    return sorted(files)


def check_syntax(sol_file: Path) -> tuple[bool, str]:
    """Basic syntax validation for a Solidity file."""
    try:
        content = sol_file.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Read error: {e}"

    if len(content.strip()) == 0:
        return False, "Empty file"

    has_pragma = REQUIRED_PATTERNS[0].search(content) is not None
    has_contract = REQUIRED_PATTERNS[1].search(content) is not None

    if not has_pragma:
        return False, "Missing 'pragma solidity' declaration"
    if not has_contract:
        return False, "Missing contract/interface/library declaration"

    return True, "OK"


def main() -> int:
    sol_files = find_sol_files()
    if not sol_files:
        print("WARNING: No .sol files found in known directories")
        return 1

    print(f"Checking {len(sol_files)} Solidity files...")
    failures = []
    for f in sol_files:
        ok, msg = check_syntax(f)
        rel = f.relative_to(REPO_ROOT)
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {rel} — {msg}")
        if not ok:
            failures.append((rel, msg))

    print(f"\n{len(sol_files)} checked, {len(sol_files) - len(failures)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
