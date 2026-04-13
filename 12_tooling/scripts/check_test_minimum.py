#!/usr/bin/env python3
"""Test Minimum Enforcement Check - fail if productive .py module lacks any test file.

Rules:
- For each root module dir (NN_<name>/ pattern), find *.py files directly in the module dir (not subdirs)
- Skip: __init__.py, __pycache__, files in tests/ already
- For each module file X.py, check if tests/test_X.py exists in same module dir
- Exit 0 if all have tests, Exit 1 with list of untested modules
"""

import os
import re
import sys

# Directories to skip entirely (relative to repo root)
SKIP_DIRS = {".ssid_sandbox", ".claude", "__pycache__", "scripts", "docs"}

# Module dir pattern: NN_<name>
MODULE_DIR_PATTERN = re.compile(r"^\d{2}_")


def find_module_dirs(repo_root: str) -> list[str]:
    """Return absolute paths of top-level module directories matching NN_ pattern."""
    results = []
    for entry in sorted(os.listdir(repo_root)):
        if entry in SKIP_DIRS:
            continue
        if not MODULE_DIR_PATTERN.match(entry):
            continue
        full = os.path.join(repo_root, entry)
        if os.path.isdir(full):
            results.append(full)
    return results


def find_productive_py_files(module_dir: str) -> list[str]:
    """Return stems of productive .py files directly in module_dir (no subdirs)."""
    stems = []
    try:
        entries = os.listdir(module_dir)
    except PermissionError:
        return stems
    for entry in entries:
        if not entry.endswith(".py"):
            continue
        if entry.startswith("__"):
            continue  # skip __init__.py, __main__.py, etc.
        if entry.startswith("test_"):
            continue  # skip any test files accidentally placed at module root
        full = os.path.join(module_dir, entry)
        if os.path.isfile(full):
            stems.append(os.path.splitext(entry)[0])
    return stems


def has_test_file(module_dir: str, stem: str) -> bool:
    """Check if tests/test_<stem>.py or test_<stem>.py exists in module's tests/ dir.

    Also accepts partial stem matches: e.g., test_governance_reward.py matches
    governance_reward_engine.py (extract prefix: first word before _engine, _router, etc.)
    """
    from pathlib import Path
    tests_dir = Path(module_dir) / "tests"
    candidates = [
        tests_dir / f"test_{stem}.py",
        tests_dir / f"test_{stem}_src.py",
    ]
    if any(c.is_file() for c in candidates):
        return True
    for suffix in ["_engine", "_router", "_splitter", "_handler", "_distributor"]:
        if stem.endswith(suffix):
            prefix = stem[:-len(suffix)]
            test_file = tests_dir / f"test_{prefix}.py"
            if test_file.is_file():
                return True
            break
    return False


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    module_dirs = find_module_dirs(repo_root)

    total_modules = 0
    covered_modules = 0
    violations: list[tuple[str, str]] = []  # (module_dir_name, stem)

    for module_dir in module_dirs:
        dir_name = os.path.basename(module_dir)
        stems = find_productive_py_files(module_dir)
        for stem in stems:
            total_modules += 1
            if has_test_file(module_dir, stem):
                covered_modules += 1
            else:
                violations.append((dir_name, stem))

    uncovered = total_modules - covered_modules

    print("=" * 60)
    print("TEST MINIMUM ENFORCEMENT - SSID Coverage Check")
    print("=" * 60)
    print(f"  Productive modules found : {total_modules}")
    print(f"  Covered (have test file) : {covered_modules}")
    print(f"  Uncovered (violations)   : {uncovered}")
    print()

    if violations:
        print("VIOLATIONS — missing tests/test_<module>.py:")
        for dir_name, stem in violations:
            print(f"  MISSING  {dir_name}/{stem}.py  ->  {dir_name}/tests/test_{stem}.py")
        print()
        coverage_pct = (covered_modules / total_modules * 100) if total_modules else 0
        print(f"Coverage: {coverage_pct:.1f}%  ({covered_modules}/{total_modules})")
        print()
        print("FAIL: Test minimum not met. Add test files for each violation above.")
        return 1
    else:
        coverage_pct = 100.0 if total_modules > 0 else 100.0
        print(f"Coverage: {coverage_pct:.1f}%  ({covered_modules}/{total_modules})")
        print()
        print("PASS: All productive modules have at least one test file.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
