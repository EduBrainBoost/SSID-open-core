#!/usr/bin/env python3
"""Verify public mirror — checks that no private content leaked into OpenCore."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple


PRIVATE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Windows workspace paths", re.compile(r"C:\\Users\\bibel\\SSID-Workspace")),
    ("Windows docs paths", re.compile(r"C:\\Users\\bibel\\Documents\\Github")),
    ("MAOS internals", re.compile(r"\bMAOS\b", re.IGNORECASE)),
    ("Agent-Swarm", re.compile(r"\bAgent-Swarm\b", re.IGNORECASE)),
    ("Private registry references", re.compile(r"private.*registry", re.IGNORECASE)),
    ("Hermes runtime state", re.compile(r"Hermes.*runtime", re.IGNORECASE)),
    ("Jarvis personal runtime", re.compile(r"Jarvis.*runtime", re.IGNORECASE)),
    ("OmniRoot internals", re.compile(r"\bOmniRoot\b", re.IGNORECASE)),
    ("API keys (values)", re.compile(r"(?i)(api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9]{16,}")),
    ("Secret keys", re.compile(r"(?i)(secret[_-]?key)\s*[:=]\s*['\"]?[^\s]{16,}")),
    ("Password literals", re.compile(r"(?i)(password)\s*[:=]\s*['\"]?[^\s]{4,}")),
]

EXEMPT_FILES = {
    "23_compliance/policies/opencore_policy.yaml",
    "11_test_simulation/unit/test_opencore_policy.py",
    "12_tooling/scripts/verify_private_leakage.py",
    ".github/workflows/security.yaml",
    "_build_structure.py",
    "05_documentation/contributing.py",
}


def verify_public_mirror(repo_root: Path | str = ".") -> dict:
    root = Path(repo_root)
    violations: List[dict] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        if rel in EXEMPT_FILES:
            continue
        if path.suffix in {".pyc", ".exe", ".dll", ".so", ".bin"}:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for name, pattern in PRIVATE_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                violations.append({
                    "file": rel,
                    "pattern": name,
                    "matches": matches[:3],  # Cap at 3 matches
                })

    result = {
        "verified_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "total_files_scanned": len(list(root.rglob("*"))),
        "violations_found": len(violations),
        "violations": violations,
        "status": "PASS" if not violations else "FAIL",
    }
    return result


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    result = verify_public_mirror(repo)
    print(f"Status: {result['status']}")
    print(f"Files scanned: {result['total_files_scanned']}")
    print(f"Violations: {result['violations_found']}")
    for v in result["violations"]:
        print(f"  - {v['file']}: {v['pattern']} -> {v['matches']}")
    sys.exit(0 if result["status"] == "PASS" else 1)
