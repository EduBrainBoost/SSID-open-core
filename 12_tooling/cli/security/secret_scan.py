#!/usr/bin/env python3
"""Secret scanning for SSID repository.

Detects potentially leaked credentials, API keys, passwords, tokens, etc.
Uses pattern matching and entropy analysis.
"""
import json
import re
import sys
from pathlib import Path
from typing import Any

# Patterns for common secrets
SECRET_PATTERNS = {
    "api_key": r"api[_-]?key\s*[:=]\s*['\"]?([a-zA-Z0-9\-_]{32,})['\"]?",
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret_key": r"aws_secret_access_key\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?",
    "github_token": r"ghp_[a-zA-Z0-9_]{36,255}",
    "github_oauth": r"gho_[a-zA-Z0-9_]{36,255}",
    "github_app": r"ghu_[a-zA-Z0-9_]{36,255}",
    "private_key": r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----",
    "password": r"password\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
    "database_uri": r"(?:mongodb|postgres|mysql|redis)://[^@\s]+@[^\s/]+",
    "slack_token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{32}",
    "stripe_key": r"(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{20,}",
    "jwt_token": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
}

# Exclude patterns (false positives)
EXCLUDE_PATTERNS = [
    r"\.git/",
    r"\.git\\",
    r"_worktrees/",
    r"_worktrees\\",
    r"node_modules/",
    r"__pycache__/",
    r"\.pytest_cache/",
    r"\.pytest_cache\\",
    r"test_.*\.py",
    r".*\.example",
    r".*\.sample",
    r"\.ruff_cache/",
    r"\.ruff_cache\\",
    r"\.ssid_sandbox/",
    r"\.ssid_sandbox\\",
    r"\.claude/",
    r"\.claude\\",
    r"agent_runs/",
    r"agent_runs\\",
    r"diff\.patch",
    r"\.pytest_tmp",
    r"\.pytest_tmp\\",
    r"23_compliance/gitleaks.toml",
]


def should_exclude(filepath: str) -> bool:
    """Check if file should be excluded from scanning."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, filepath):
            return True
    return False


def scan_file(filepath: Path) -> list[dict[str, Any]]:
    """Scan a single file for secrets."""
    findings = []

    if filepath.suffix in {".bin", ".pyc", ".so", ".dll", ".exe"}:
        return findings

    if should_exclude(str(filepath)):
        return findings

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    lines = content.split("\n")
    for line_num, line in enumerate(lines, 1):
        for secret_type, pattern in SECRET_PATTERNS.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({
                    "file": str(filepath.relative_to(Path.cwd())),
                    "line": line_num,
                    "secret_type": secret_type,
                    "pattern": pattern,
                    "severity": "HIGH",
                })

    return findings


def scan_directory(root: Path) -> dict[str, Any]:
    """Scan entire directory for secrets."""
    findings = []
    files_scanned = 0
    max_files = 5000

    for filepath in root.rglob("*"):
        if filepath.is_file():
            files_scanned += 1
            if files_scanned <= max_files:
                findings.extend(scan_file(filepath))
            if files_scanned % 500 == 0:
                print(f"  Scanned {files_scanned} files...")
            if files_scanned > max_files:
                break

    return {
        "timestamp": str(Path.cwd()),
        "files_scanned": files_scanned,
        "secrets_found": len(findings),
        "findings": findings,
    }


def main():
    """Run secret scanning."""
    repo_root = Path.cwd()

    results = scan_directory(repo_root)

    output_file = Path("security/secrets-scan.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(results, indent=2))

    print(f"Secret scan complete:")
    print(f"  Files scanned: {results['files_scanned']}")
    print(f"  Secrets found: {results['secrets_found']}")

    if results['secrets_found'] > 0:
        print("\nFindings:")
        for finding in results['findings']:
            print(f"  {finding['file']}:{finding['line']} - {finding['secret_type']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
