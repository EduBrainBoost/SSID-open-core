# DEPRECATED: REDUNDANT — Canonical tool is 12_tooling/cli/duplicate_guard.py
#!/usr/bin/env python3
"""
duplicate_rule_checker.py - Scans for duplicate rule definitions across the SSID repository.

Checks:
  1. Duplicate rule names in .rego policy files
  2. Duplicate function names in .py validator files
  3. Duplicate rule_ids in .yaml compliance contracts

Exit codes:
  0 - No duplicates found (clean)
  1 - Duplicates detected
  2 - Scan error
"""

import os
import re
import sys
import ast
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGO_DIRS = [
    REPO_ROOT / "23_compliance" / "policies",
    REPO_ROOT / "07_governance_legal" / "policies" / "rego",
]
VALIDATOR_DIRS = [
    REPO_ROOT / "23_compliance" / "validators",
    REPO_ROOT / "23_compliance" / "src",
]
CONTRACT_DIRS = [
    REPO_ROOT / "23_compliance" / "contracts",
]


def find_files(directories: List[Path], extension: str) -> List[Path]:
    """Recursively find files with a given extension in the listed directories."""
    results = []
    for base_dir in directories:
        if not base_dir.exists():
            continue
        for root, _dirs, files in os.walk(base_dir):
            for f in files:
                if f.endswith(extension):
                    results.append(Path(root) / f)
    return sorted(results)


def scan_rego_duplicates() -> Dict[str, List[Tuple[str, int]]]:
    """
    Scan .rego files for duplicate rule names.
    A Rego rule is defined as: <name>[<args>] { or <name> = <value> {
    We track rule names per package and flag duplicates across files.
    """
    rule_pattern = re.compile(
        r"^(?!#)(?!\s*#)"
        r"\s*([a-zA-Z_]\w*)"
        r"\s*(?:\[.*?\])?"
        r"\s*(?:=\s*\S+)?"
        r"\s*\{",
        re.MULTILINE,
    )

    rule_locations: Dict[str, List[Tuple[str, int]]] = {}
    rego_files = find_files(REGO_DIRS, ".rego")

    for fpath in rego_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(content.splitlines(), start=1):
            m = rule_pattern.match(line)
            if m:
                rule_name = m.group(1)
                if rule_name in ("package", "import", "default", "not", "some",
                                 "every", "if", "else", "with"):
                    continue
                key = rule_name
                if key not in rule_locations:
                    rule_locations[key] = []
                rule_locations[key].append((str(fpath.relative_to(REPO_ROOT)), i))

    return {k: v for k, v in rule_locations.items() if len(v) > 1}


def scan_validator_duplicates() -> Dict[str, List[Tuple[str, int]]]:
    """
    Scan .py validator files for duplicate function names using AST parsing.
    Reports functions defined with the same name across different validator files.
    """
    func_locations: Dict[str, List[Tuple[str, int]]] = {}
    py_files = find_files(VALIDATOR_DIRS, ".py")

    for fpath in py_files:
        try:
            source = fpath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(fpath))
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                fname = node.name
                if fname.startswith("__") and fname.endswith("__"):
                    continue
                if fname not in func_locations:
                    func_locations[fname] = []
                func_locations[fname].append(
                    (str(fpath.relative_to(REPO_ROOT)), node.lineno)
                )

    return {k: v for k, v in func_locations.items() if len(v) > 1}


def scan_contract_duplicates() -> Dict[str, List[Tuple[str, int]]]:
    """
    Scan .yaml contract files for duplicate rule_id values.
    Looks for 'rule_id' keys in YAML structures and flags collisions.
    """
    try:
        import yaml
    except ImportError:
        return _scan_contract_duplicates_regex()

    rule_id_locations: Dict[str, List[Tuple[str, int]]] = {}
    yaml_files = find_files(CONTRACT_DIRS, ".yaml")

    for fpath in yaml_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            docs = list(yaml.safe_load_all(content))
        except (OSError, yaml.YAMLError):
            continue

        _extract_rule_ids(docs, str(fpath.relative_to(REPO_ROOT)), rule_id_locations)

    return {k: v for k, v in rule_id_locations.items() if len(v) > 1}


def _extract_rule_ids(obj, filepath: str, acc: Dict[str, List[Tuple[str, int]]]):
    """Recursively extract rule_id values from parsed YAML."""
    if isinstance(obj, dict):
        if "rule_id" in obj:
            rid = str(obj["rule_id"])
            if rid not in acc:
                acc[rid] = []
            acc[rid].append((filepath, 0))
        for v in obj.values():
            _extract_rule_ids(v, filepath, acc)
    elif isinstance(obj, list):
        for item in obj:
            _extract_rule_ids(item, filepath, acc)


def _scan_contract_duplicates_regex() -> Dict[str, List[Tuple[str, int]]]:
    """Fallback regex-based rule_id scanner when PyYAML is not available."""
    pattern = re.compile(r"rule_id\s*:\s*[\"']?([A-Za-z0-9_.-]+)[\"']?")
    rule_id_locations: Dict[str, List[Tuple[str, int]]] = {}
    yaml_files = find_files(CONTRACT_DIRS, ".yaml")

    for fpath in yaml_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(content.splitlines(), start=1):
            m = pattern.search(line)
            if m:
                rid = m.group(1)
                if rid not in rule_id_locations:
                    rule_id_locations[rid] = []
                rule_id_locations[rid].append((str(fpath.relative_to(REPO_ROOT)), i))

    return {k: v for k, v in rule_id_locations.items() if len(v) > 1}


def print_section(title: str, duplicates: Dict[str, List[Tuple[str, int]]]) -> bool:
    """Print a section of duplicate findings. Returns True if duplicates exist."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

    if not duplicates:
        print("  CLEAN - No duplicates found.")
        return False

    for name, locations in sorted(duplicates.items()):
        print(f"\n  DUPLICATE: {name}")
        for filepath, line in locations:
            line_str = f":{line}" if line > 0 else ""
            print(f"    -> {filepath}{line_str}")

    print(f"\n  Total duplicate names: {len(duplicates)}")
    return True


def main() -> int:
    print(f"SSID Duplicate Rule Checker")
    print(f"Run: {datetime.now(timezone.utc).isoformat()}")
    print(f"Repo: {REPO_ROOT}")

    has_dupes = False

    rego_dupes = scan_rego_duplicates()
    if print_section("Rego Policy Rule Names (.rego)", rego_dupes):
        has_dupes = True

    validator_dupes = scan_validator_duplicates()
    if print_section("Validator Function Names (.py)", validator_dupes):
        has_dupes = True

    contract_dupes = scan_contract_duplicates()
    if print_section("Contract Rule IDs (.yaml)", contract_dupes):
        has_dupes = True

    print(f"\n{'='*60}")
    if has_dupes:
        print("  RESULT: DUPLICATES FOUND - review required")
        return 1
    else:
        print("  RESULT: CLEAN - no duplicates detected")
        return 0


if __name__ == "__main__":
    sys.exit(main())
