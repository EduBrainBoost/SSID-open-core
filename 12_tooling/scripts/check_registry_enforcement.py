#!/usr/bin/env python3
"""Registry Enforcement Check — fail if productive .py module lacks module.yaml registry entry.

Rules:
- Scan all root-level module dirs (01_ai_layer through 24_meta_orchestration)
- For each *.py file directly in the module dir (not in subdirs like tests/, shards/, __pycache__)
- Check that module.yaml exists in same dir
- Check that the module stem name appears in module.yaml (registry block or module_id or similar)
- Exit 0 if all clean, Exit 1 with list of violations
"""

import os
import re
import sys

# Dirs/patterns to skip entirely
SKIP_DIRS = {"__pycache__", "tests", ".ssid_sandbox", ".claude", "shards"}

# .py files to skip (utility / non-productive)
SKIP_FILES = {"__init__.py", "conftest.py"}

# Pattern for module dirs: NN_name
MODULE_DIR_RE = re.compile(r"^\d{2}_")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_module_dirs(root: str) -> list[str]:
    """Return all top-level dirs matching NN_ pattern."""
    result = []
    for name in sorted(os.listdir(root)):
        if MODULE_DIR_RE.match(name):
            full = os.path.join(root, name)
            if os.path.isdir(full):
                result.append(full)
    return result


def get_productive_py_files(module_dir: str) -> list[str]:
    """Return .py files directly in module_dir, skipping non-productive ones."""
    result = []
    try:
        entries = os.listdir(module_dir)
    except PermissionError:
        return result

    for entry in sorted(entries):
        if not entry.endswith(".py"):
            continue
        if entry in SKIP_FILES:
            continue
        # Skip test files at module root (they belong to test suites, not registry)
        if entry.startswith("test_"):
            continue
        full = os.path.join(module_dir, entry)
        if os.path.isfile(full):
            result.append(entry)
    return result


def check_registry_entry(module_dir: str, py_stem: str) -> tuple[bool, str]:
    """
    Check that module.yaml exists and contains the py_stem.

    Returns (ok: bool, reason: str).
    The check looks for the stem in any of:
      - registry.id fields
      - registry.modules[].id fields
      - import_path values
      - plain text occurrence of the stem
    """
    yaml_path = os.path.join(module_dir, "module.yaml")
    if not os.path.isfile(yaml_path):
        return False, "module.yaml missing"

    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        return False, f"Cannot read module.yaml: {exc}"

    # Fast text scan: stem must appear literally somewhere in module.yaml
    # (covers all registry formats: flat list, nested modules list, import_path, etc.)
    if py_stem in content:
        return True, "ok"

    return False, f"stem '{py_stem}' not found in module.yaml"


def main() -> int:
    violations: list[str] = []
    checked = 0

    module_dirs = find_module_dirs(REPO_ROOT)

    for module_dir in module_dirs:
        mod_name = os.path.basename(module_dir)
        py_files = get_productive_py_files(module_dir)

        for py_file in py_files:
            stem = py_file[:-3]  # strip .py
            ok, reason = check_registry_entry(module_dir, stem)
            checked += 1
            if not ok:
                rel = os.path.relpath(os.path.join(module_dir, py_file), REPO_ROOT).replace("\\", "/")
                violations.append(f"  VIOLATION  {rel}  [{reason}]")

    print(f"Registry Enforcement Check — scanned {checked} productive .py file(s) across {len(module_dirs)} module dirs")
    print()

    if violations:
        print(f"FAIL: {len(violations)} violation(s) found:\n")
        for v in violations:
            print(v)
        print()
        print("ACTION REQUIRED: Add registry entries to the relevant module.yaml files.")
        print("  Registry block format (flat):  registry:\n    - id: <stem>")
        print("  Registry block format (nested): registry:\n    modules:\n      - id: <stem>")
        return 1

    print("PASS: All productive .py modules have registry entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
