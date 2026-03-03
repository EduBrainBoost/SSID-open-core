#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _read_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _collect_matches(lines: Iterable[str], pattern: re.Pattern[str]) -> Dict[str, List[int]]:
    out: Dict[str, List[int]] = defaultdict(list)
    for idx, line in enumerate(lines, start=1):
        m = pattern.search(line)
        if m:
            out[m.group(1)].append(idx)
    return out


def _find_dups(mapping: Dict[str, List[int]]) -> Dict[str, List[int]]:
    return {k: v for k, v in mapping.items() if len(v) > 1}


def _check_yaml_rule_ids(path: Path) -> List[str]:
    lines = _read_lines(path)
    pat = re.compile(r"\brule_id\s*:\s*['\"]?([A-Za-z0-9_.:-]+)['\"]?")
    dups = _find_dups(_collect_matches(lines, pat))
    findings: List[str] = []
    for rid, line_nums in sorted(dups.items()):
        for line_no in line_nums:
            findings.append(f"{path.as_posix()}:{line_no} duplicate rule_id '{rid}'")
    return findings


def _check_python_function_dups(path: Path, label: str) -> List[str]:
    if not path.exists():
        return []
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    seen: Dict[str, List[int]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            seen[node.name].append(node.lineno)
    findings: List[str] = []
    for name, line_nums in sorted(_find_dups(seen).items()):
        for line_no in line_nums:
            findings.append(f"{path.as_posix()}:{line_no} duplicate {label} '{name}'")
    return findings


def _check_rego_rule_ids(path: Path) -> List[str]:
    lines = _read_lines(path)
    pat = re.compile(r"\brule_id\s*[:=]\s*['\"]([A-Za-z0-9_.:-]+)['\"]")
    dups = _find_dups(_collect_matches(lines, pat))
    findings: List[str] = []
    for rid, line_nums in sorted(dups.items()):
        for line_no in line_nums:
            findings.append(f"{path.as_posix()}:{line_no} duplicate rego rule_id '{rid}'")
    return findings


def _check_cli_dups(path: Path) -> List[str]:
    lines = _read_lines(path)
    cmd_pat = re.compile(r"add_parser\(\s*['\"]([A-Za-z0-9_-]+)['\"]")
    flag_pat = re.compile(r"add_argument\(\s*['\"](--[A-Za-z0-9_-]+)['\"]")
    cmd_dups = _find_dups(_collect_matches(lines, cmd_pat))
    flag_dups = _find_dups(_collect_matches(lines, flag_pat))
    findings: List[str] = []
    for name, line_nums in sorted(cmd_dups.items()):
        for line_no in line_nums:
            findings.append(f"{path.as_posix()}:{line_no} duplicate CLI command '{name}'")
    for flag, line_nums in sorted(flag_dups.items()):
        for line_no in line_nums:
            findings.append(f"{path.as_posix()}:{line_no} duplicate CLI flag '{flag}'")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="SSID Duplicate Guard (PASS/FAIL only).")
    parser.add_argument("--repo-root", default=".", help="Repo root path")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    checks: List[Tuple[str, List[str]]] = [
        ("yaml_rule_id", _check_yaml_rule_ids(root / "16_codex" / "contracts" / "sot" / "sot_contract.yaml")),
        (
            "python_functions",
            _check_python_function_dups(root / "03_core" / "validators" / "sot" / "sot_validator_core.py", "python function"),
        ),
        ("rego_rule_id", _check_rego_rule_ids(root / "23_compliance" / "policies" / "sot" / "sot_policy.rego")),
        ("cli_commands_flags", _check_cli_dups(root / "12_tooling" / "cli" / "sot_validator.py")),
        (
            "test_functions",
            _check_python_function_dups(
                root / "11_test_simulation" / "tests_compliance" / "test_sot_validator.py",
                "test function",
            ),
        ),
    ]

    findings: List[str] = []
    for _, f in checks:
        findings.extend(f)

    if findings:
        print("FAIL")
        for line in findings:
            print(line)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
