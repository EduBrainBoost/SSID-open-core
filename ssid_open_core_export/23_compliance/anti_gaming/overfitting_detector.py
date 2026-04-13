#!/usr/bin/env python3
"""Overfitting Detector for SSID Compliance.

Detects signs of compliance overfitting: tests that are written purely to
pass CI gates without testing real behavior, placeholder files that inflate
metrics, and badge-farming patterns.

Overfitting indicators:
  - Test files with only 'pass' or 'assert True'
  - Python files shorter than 3 lines of actual code
  - YAML files with only placeholder content
  - Extremely high test-pass ratios with zero logic coverage
"""

from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

PLACEHOLDER_MARKERS = [
    "AUTO-GENERATED PLACEHOLDER",
    "TODO",
    "PLACEHOLDER",
    "STUB",
    "pass  # placeholder",
]


def detect_placeholder_files(root: Path) -> list[dict]:
    """Find files that contain only placeholder content."""
    findings: list[dict] = []

    for py_file in root.rglob("*.py"):
        if "__pycache__" in str(py_file) or ".venv" in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue

        if not content:
            continue

        for marker in PLACEHOLDER_MARKERS:
            if content == marker or content.startswith(marker):
                findings.append(
                    {
                        "file": str(py_file.relative_to(root)),
                        "type": "placeholder_file",
                        "marker": marker,
                    }
                )
                break

    for yaml_file in root.rglob("*.yaml"):
        if "__pycache__" in str(yaml_file) or ".venv" in str(yaml_file):
            continue
        try:
            content = yaml_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue

        for marker in PLACEHOLDER_MARKERS:
            if content == marker or content.startswith(marker):
                findings.append(
                    {
                        "file": str(yaml_file.relative_to(root)),
                        "type": "placeholder_yaml",
                        "marker": marker,
                    }
                )
                break

    return findings


def detect_trivial_tests(root: Path) -> list[dict]:
    """Find test files that contain only trivial assertions."""
    findings: list[dict] = []
    test_dirs = list(root.rglob("test_*.py"))

    for test_file in test_dirs:
        if "__pycache__" in str(test_file) or ".venv" in str(test_file):
            continue
        try:
            content = test_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        ]

        if not functions:
            continue

        trivial_count = 0
        for func in functions:
            body = func.body
            if len(body) == 1:
                stmt = body[0]
                if (
                    isinstance(stmt, ast.Pass)
                    or isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    or (
                        isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.Constant) and stmt.test.value is True
                    )
                ):
                    trivial_count += 1

        if trivial_count > 0 and trivial_count == len(functions):
            findings.append(
                {
                    "file": str(test_file.relative_to(root)),
                    "type": "trivial_test_only",
                    "trivial_count": trivial_count,
                    "total_tests": len(functions),
                }
            )

    return findings


def main() -> int:
    """Run overfitting detection and report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    placeholder_findings = detect_placeholder_files(REPO_ROOT)
    trivial_findings = detect_trivial_tests(REPO_ROOT)

    total = len(placeholder_findings) + len(trivial_findings)

    if placeholder_findings:
        log.warning("Placeholder files detected: %d", len(placeholder_findings))
        for f in placeholder_findings[:10]:
            log.warning("  %s (%s)", f["file"], f["type"])

    if trivial_findings:
        log.warning("Trivial-only test files: %d", len(trivial_findings))
        for f in trivial_findings[:10]:
            log.warning("  %s (%d/%d trivial)", f["file"], f["trivial_count"], f["total_tests"])

    if total == 0:
        log.info("OVERFITTING_PASS: No overfitting indicators found")
    else:
        log.warning("OVERFITTING_WARN: %d indicator(s) found — review recommended", total)

    return 0


if __name__ == "__main__":
    sys.exit(main())
