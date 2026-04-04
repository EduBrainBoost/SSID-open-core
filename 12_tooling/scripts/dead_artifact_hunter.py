# DEPRECATED: REDUNDANT — Canonical tool is 12_tooling/cli/duplicate_guard.py
#!/usr/bin/env python3
"""
dead_artifact_hunter.py - Finds dead, orphaned, and placeholder artifacts in the SSID repository.

Detects:
  1. Empty files (0 bytes)
  2. Placeholder-only files (< 50 bytes with only comments or whitespace)
  3. Orphaned test files (importing modules that do not exist)
  4. Unreferenced registry entries (registry items pointing to missing paths)

Exit codes:
  0 - Repository is clean
  1 - Dead artifacts found
  2 - Scan error
"""

import ast
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Directories to skip entirely
SKIP_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "egg-info",
}

# Extensions to scan
SCANNABLE_EXTENSIONS = {
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".rego",
    ".md",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".sh",
    ".toml",
}


class Finding:
    """Represents a single dead artifact finding."""

    def __init__(self, category: str, path: str, detail: str, severity: str = "warning"):
        self.category = category
        self.path = path
        self.detail = detail
        self.severity = severity

    def __str__(self):
        return f"[{self.severity.upper()}] {self.category}: {self.path}\n         {self.detail}"


def should_skip(dirpath: str) -> bool:
    """Check if a directory should be skipped."""
    parts = Path(dirpath).parts
    return any(p in SKIP_DIRS for p in parts)


def collect_all_files() -> list[Path]:
    """Collect all scannable files in the repository."""
    files = []
    for root, dirs, filenames in os.walk(REPO_ROOT):
        # Prune skipped directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in filenames:
            fpath = Path(root) / f
            if fpath.suffix in SCANNABLE_EXTENSIONS or f in ("Dockerfile", "Makefile"):
                files.append(fpath)
    return files


def find_empty_files(all_files: list[Path]) -> list[Finding]:
    """Find files that are exactly 0 bytes."""
    findings = []
    for fpath in all_files:
        try:
            if fpath.stat().st_size == 0:
                # __init__.py files with 0 bytes are normal
                if fpath.name == "__init__.py":
                    continue
                # .gitkeep files are intentionally empty
                if fpath.name == ".gitkeep":
                    continue
                findings.append(
                    Finding(
                        category="EMPTY_FILE",
                        path=str(fpath.relative_to(REPO_ROOT)),
                        detail="File is 0 bytes. Consider removing or adding content.",
                        severity="warning",
                    )
                )
        except OSError:
            continue
    return findings


def find_placeholder_files(all_files: list[Path]) -> list[Finding]:
    """Find files under 50 bytes that contain only comments or whitespace."""
    findings = []
    comment_patterns = [
        re.compile(r"^\s*#"),  # Python/Shell/Rego comments
        re.compile(r"^\s*//"),  # JS/TS comments
        re.compile(r"^\s*\*"),  # Block comment continuation
        re.compile(r"^\s*/\*"),  # Block comment start
        re.compile(r"^\s*<!--"),  # HTML/Markdown comments
        re.compile(r"^\s*$"),  # Empty lines
    ]

    for fpath in all_files:
        try:
            size = fpath.stat().st_size
            if size == 0 or size >= 50:
                continue
            if fpath.name == "__init__.py" or fpath.name == ".gitkeep":
                continue

            content = fpath.read_text(encoding="utf-8", errors="replace")
            lines = content.strip().splitlines()

            if not lines:
                continue  # Already caught by empty file check

            all_comments = all(any(pat.match(line) for pat in comment_patterns) for line in lines)

            if all_comments:
                findings.append(
                    Finding(
                        category="PLACEHOLDER_FILE",
                        path=str(fpath.relative_to(REPO_ROOT)),
                        detail=f"File is {size} bytes and contains only comments/whitespace. Likely a placeholder.",
                        severity="info",
                    )
                )
        except OSError:
            continue
    return findings


def find_orphaned_test_files() -> list[Finding]:
    """Find test files that import modules which do not exist in the repo."""
    findings = []
    test_dirs = []

    # Collect all test directories
    for root_dir in REPO_ROOT.iterdir():
        if not root_dir.is_dir() or root_dir.name in SKIP_DIRS:
            continue
        for sub_root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    test_dirs.append(Path(sub_root) / f)

    # Build a set of known Python module paths
    known_modules: set[str] = set()
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".py") and not f.startswith("test_"):
                # Register as module path (relative dotted)
                fpath = Path(root) / f
                rel = fpath.relative_to(REPO_ROOT)
                module_path = str(rel.with_suffix("")).replace(os.sep, ".").replace("/", ".")
                known_modules.add(module_path)
                # Also register the parent package
                parts = module_path.split(".")
                for i in range(1, len(parts)):
                    known_modules.add(".".join(parts[:i]))

    # Check each test file for imports of repo-internal modules that don't exist
    ssid_prefixes = tuple(f"{d.name}." for d in REPO_ROOT.iterdir() if d.is_dir() and re.match(r"\d{2}_", d.name))

    for test_file in test_dirs:
        try:
            source = test_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(test_file))
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            module_name: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(ssid_prefixes):
                        module_name = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(ssid_prefixes):
                module_name = node.module

            if module_name and module_name not in known_modules:
                findings.append(
                    Finding(
                        category="ORPHANED_TEST",
                        path=str(test_file.relative_to(REPO_ROOT)),
                        detail=f"Imports '{module_name}' which does not exist in the repository.",
                        severity="warning",
                    )
                )

    return findings


def find_unreferenced_registry_entries() -> list[Finding]:
    """Find registry entries that point to non-existent file paths."""
    findings = []
    registry_dirs = [
        REPO_ROOT / "23_compliance" / "policies" / "registry",
        REPO_ROOT / "16_codex",
    ]

    for reg_dir in registry_dirs:
        if not reg_dir.exists():
            continue
        for root, _dirs, files in os.walk(reg_dir):
            for f in files:
                if not (f.endswith(".yaml") or f.endswith(".yml") or f.endswith(".json")):
                    continue
                fpath = Path(root) / f
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                # Extract path-like references
                path_pattern = re.compile(
                    r"(?:path|file|source|target|ref)\s*:\s*[\"']?"
                    r"([0-9]{2}_[a-z_]+/[^\s\"'#]+)"
                )
                for i, line in enumerate(content.splitlines(), start=1):
                    m = path_pattern.search(line)
                    if m:
                        ref_path = m.group(1).rstrip("\"'")
                        full_path = REPO_ROOT / ref_path
                        if not full_path.exists():
                            findings.append(
                                Finding(
                                    category="UNREFERENCED_REGISTRY",
                                    path=str(fpath.relative_to(REPO_ROOT)),
                                    detail=f"Line {i}: references '{ref_path}' which does not exist.",
                                    severity="warning",
                                )
                            )

    return findings


def main() -> int:
    print("SSID Dead Artifact Hunter")
    print(f"Run: {datetime.now(UTC).isoformat()}")
    print(f"Repo: {REPO_ROOT}")
    print(f"{'=' * 60}")

    all_files = collect_all_files()
    print(f"Scanned files: {len(all_files)}")

    all_findings: list[Finding] = []

    # Run all checks
    print("\n[1/4] Scanning for empty files...")
    empty = find_empty_files(all_files)
    all_findings.extend(empty)
    print(f"       Found: {len(empty)}")

    print("[2/4] Scanning for placeholder files...")
    placeholders = find_placeholder_files(all_files)
    all_findings.extend(placeholders)
    print(f"       Found: {len(placeholders)}")

    print("[3/4] Scanning for orphaned test files...")
    orphans = find_orphaned_test_files()
    all_findings.extend(orphans)
    print(f"       Found: {len(orphans)}")

    print("[4/4] Scanning for unreferenced registry entries...")
    unreferenced = find_unreferenced_registry_entries()
    all_findings.extend(unreferenced)
    print(f"       Found: {len(unreferenced)}")

    # Report
    print(f"\n{'=' * 60}")
    print("  FINDINGS REPORT")
    print(f"{'=' * 60}")

    if not all_findings:
        print("\n  CLEAN - No dead artifacts detected.")
        return 0

    by_category: dict[str, list[Finding]] = {}
    for f in all_findings:
        by_category.setdefault(f.category, []).append(f)

    for category, items in sorted(by_category.items()):
        print(f"\n  --- {category} ({len(items)}) ---")
        for item in items:
            print(f"  {item}")

    total = len(all_findings)
    warnings = sum(1 for f in all_findings if f.severity == "warning")
    infos = sum(1 for f in all_findings if f.severity == "info")

    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {total} findings ({warnings} warnings, {infos} info)")
    print("  RESULT: DEAD ARTIFACTS FOUND - cleanup recommended")
    return 1


if __name__ == "__main__":
    sys.exit(main())
