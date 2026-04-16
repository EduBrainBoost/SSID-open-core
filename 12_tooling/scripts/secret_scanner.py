#!/usr/bin/env python3
"""Secret scanner for PII and sensitive credential detection."""

import argparse
import json
import re
import sys
from pathlib import Path


# Pattern definitions for secret detection
PATTERNS = {
    "aws_key": {
        "pattern": r"AKIA[0-9A-Z]{16}",
        "pattern_name": "AWS Access Key",
        "severity": "critical"
    },
    "github_pat": {
        "pattern": r"ghp_[a-zA-Z0-9]{36,255}",
        "pattern_name": "GitHub Personal Access Token",
        "severity": "critical"
    },
    "github_oauth": {
        "pattern": r"gho_[a-zA-Z0-9]{36,255}",
        "pattern_name": "GitHub OAuth Token",
        "severity": "critical"
    },
    "private_key": {
        "pattern": r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY",
        "pattern_name": "Private Key",
        "severity": "critical"
    },
    "slack_token": {
        "pattern": r"xoxb-[0-9]{9,12}-[a-zA-Z0-9]+",
        "pattern_name": "Slack Token",
        "severity": "critical"
    },
    "api_key": {
        "pattern": r"api[_-]?key\s*[=:]\s*['\"]?[a-zA-Z0-9]{20,}['\"]?",
        "pattern_name": "API Key",
        "severity": "high"
    },
    "password_literal": {
        "pattern": r"(?:password|passwd|pwd)\s*[=:]\s*['\"]([^'\"]{6,})['\"]",
        "pattern_name": "Password Literal",
        "severity": "high"
    },
}

# Patterns that should NOT trigger false positives
EXCLUDE_PATTERNS = [
    r"#.*sha256",  # Hash in comment
    r"#.*hash",    # Hash reference
    r"test.*fixture",  # Test fixtures
]


def is_excluded(content: str) -> bool:
    """Check if content matches exclude patterns."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def scan_file(file_path: Path) -> list:
    """Scan a single file for secrets."""
    secrets = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return secrets

    # Skip files that are marked as test-fixtures
    if "ssid:test-fixture" in content:
        return secrets

    for pattern_key, pattern_def in PATTERNS.items():
        matches = re.finditer(pattern_def["pattern"], content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Check if this match is in an excluded context
            line_start = content.rfind("\n", 0, match.start()) + 1
            line_end = content.find("\n", match.end())
            if line_end == -1:
                line_end = len(content)
            line = content[line_start:line_end]

            if is_excluded(line):
                continue

            secrets.append({
                "file": str(file_path),
                "pattern_name": pattern_def["pattern_name"],
                "severity": pattern_def["severity"],
                "line": line.strip()[:100],  # Truncate for safety
                "position": match.start(),
            })

    return secrets


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scan files for secrets and PII")
    parser.add_argument("--repo-root", required=True, help="Repository root to scan")
    parser.add_argument("--scan-all", default="false", help="Scan all files")
    parser.add_argument("--exclude", nargs="*", default=[".git", "__pycache__", ".pytest_cache"],
                        help="Directories to exclude")

    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    all_secrets = []

    # Scan all Python files in repo
    for py_file in repo_root.rglob("*.py"):
        # Skip excluded directories
        if any(excl in str(py_file) for excl in args.exclude):
            continue

        secrets = scan_file(py_file)
        all_secrets.extend(secrets)

    # Output JSON
    result = {
        "total_secrets": len(all_secrets),
        "secrets": all_secrets,
    }

    print(json.dumps(result))

    # Exit with code 1 if secrets found
    return 1 if all_secrets else 0


if __name__ == "__main__":
    sys.exit(main())
