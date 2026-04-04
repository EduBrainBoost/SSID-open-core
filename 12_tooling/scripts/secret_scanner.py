#!/usr/bin/env python3
"""
AR-08: Secret Scanner based on opencore_export_policy.yaml patterns
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# From opencore_export_policy.yaml: secret_scan_regex
PATTERNS = [
    {"name": "rsa_private_key", "regex": r"BEGIN (RSA|OPENSSH|EC) PRIVATE KEY"},
    {"name": "generic_private_key", "regex": r"-----BEGIN PRIVATE KEY-----"},
    {"name": "aws_access_key", "regex": r"AKIA[0-9A-Z]{16}"},
    {"name": "slack_token", "regex": r"xox[baprs]-[0-9A-Za-z\-]{10,}"},
    {"name": "github_pat", "regex": r"ghp_[A-Za-z0-9]{36}"},
]

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".ttf", ".bin"}


def scan_file(path: Path) -> list:
    if path.suffix in SKIP_EXTS:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings = []
    for pattern in PATTERNS:
        if re.search(pattern["regex"], text):
            findings.append(
                {
                    "pattern_name": pattern["name"],
                    "file": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return findings


def scan_repo(root: Path, scan_all=False, changed_files=None) -> dict:
    secrets = []
    if scan_all:
        candidates = [p for p in root.rglob("*") if p.is_file() and not any(s in p.parts for s in SKIP_DIRS)]
    else:
        candidates = [root / f for f in (changed_files or []) if (root / f).is_file()]

    for p in candidates:
        secrets.extend(scan_file(p))

    return {"secrets": secrets, "total_secrets": len(secrets), "total_scanned": len(list(candidates))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--scan-all", default="false")
    parser.add_argument("--changed-files", default="")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    changed = [f for f in args.changed_files.split() if f]
    result = scan_repo(root, scan_all=args.scan_all.lower() == "true", changed_files=changed)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["total_secrets"] > 0 else 0)
