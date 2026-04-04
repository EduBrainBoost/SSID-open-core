"""Validator: structure_policy
Source policy: 23_compliance/policies/structure/structure_policy.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""

import re
from typing import Any

# Valid top-level SSID shard directories (from SSID structure docs)
VALID_SHARD_PREFIXES = tuple(f"{n:02d}_" for n in range(1, 30)) + (
    ".claude/",
    ".github/",
    "repair-run-evidence/",
    "sot-truth-output/",
    "sot-sync-output/",
)

# Basic filename convention: lowercase with underscores, hyphens, dots
VALID_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.]*$")


def validate_structure_policy(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validates data against structure_policy (v4.1).
    Derived from: 23_compliance/policies/structure/structure_policy.rego

    Returns (True, []) if all file paths conform to SSID structure conventions,
    otherwise (False, [violations]).
    """
    violations: list[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    file_paths: list[str] = data.get("file_paths", [])
    files: list[dict] = data.get("files", [])

    for path in file_paths:
        if not isinstance(path, str):
            violations.append(f"file_path entry is not a string: {type(path).__name__}")
            continue
        # Path must start with a valid shard prefix or known top-level dir
        if not any(path.startswith(prefix) for prefix in VALID_SHARD_PREFIXES):
            violations.append(f"Path '{path}' does not start with a valid shard prefix")

    for f in files:
        if not isinstance(f, dict):
            continue
        name = f.get("name") or ""
        if name and not VALID_FILENAME_PATTERN.match(name):
            violations.append(f"Filename '{name}' does not match naming convention")

    return (len(violations) == 0, violations)
