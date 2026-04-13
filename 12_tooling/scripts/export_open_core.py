#!/usr/bin/env python3
"""AGENT 10 — Open-Core Export Script (Python).

Exports allowed paths from the SSID repo to a target directory,
enforcing the opencore_policy.yaml and open_core_export_allowlist.yaml.

Replaces the legacy export_open_core.sh with a Python equivalent
that integrates policy validation directly.

SoT v4.1.0 | ROOT-24-LOCK | Classification: Tooling

Usage:
    python export_open_core.py --target /path/to/output [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict:
    """Load a YAML file safely."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_allowlist(repo: Path) -> dict:
    """Load the open-core export allowlist."""
    path = repo / "23_compliance" / "policies" / "open_core_export_allowlist.yaml"
    return load_yaml(path)


def load_policy(repo: Path) -> dict:
    """Load the open-core export policy."""
    path = repo / "23_compliance" / "policies" / "opencore_policy.yaml"
    return load_yaml(path)


def get_allowed_paths(allowlist: dict) -> list[str]:
    """Extract allowed paths from the allowlist."""
    paths = []
    for f in allowlist.get("root_files", []):
        paths.append(f)
    for p in allowlist.get("allowed_paths", []):
        paths.append(p)
    return paths


def is_extension_allowed(filepath: Path, policy: dict) -> bool:
    """Check if a file extension is in the allowlist and not in denylist."""
    ext = filepath.suffix.lower()
    denylist = set(policy.get("extension_denylist", []))
    if ext in denylist:
        return False
    allowlist = set(policy.get("extension_allowlist", []))
    if not allowlist:
        return True
    return ext in allowlist or ext == ""


def scan_forbidden_content(filepath: Path, policy: dict) -> list[str]:
    """Check file for forbidden content patterns."""
    patterns = policy.get("forbidden_content_patterns", [])
    if not patterns:
        return []

    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    violations = []
    for pat in patterns:
        if re.search(pat, text):
            violations.append(pat)
    return violations


def export(repo: Path, target: Path, dry_run: bool = False) -> dict:
    """Run the export. Returns report dict."""
    allowlist = load_allowlist(repo)
    policy = load_policy(repo)
    allowed = get_allowed_paths(allowlist)

    copied = []
    skipped = []
    blocked = []

    for allowed_path in allowed:
        src = repo / allowed_path
        if src.is_file():
            candidates = [src]
        elif src.is_dir():
            candidates = [f for f in src.rglob("*") if f.is_file()]
        else:
            skipped.append({"path": allowed_path, "reason": "not_found"})
            continue

        for candidate in candidates:
            rel = candidate.relative_to(repo)

            # Extension check
            if not is_extension_allowed(candidate, policy):
                blocked.append({"path": str(rel), "reason": "extension_denied"})
                continue

            # Forbidden content check
            violations = scan_forbidden_content(candidate, policy)
            if violations:
                blocked.append({"path": str(rel), "reason": "forbidden_content", "patterns": violations})
                continue

            # Copy
            dest = target / rel
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, dest)

            copied.append(str(rel))

    return {
        "copied_count": len(copied),
        "skipped_count": len(skipped),
        "blocked_count": len(blocked),
        "copied": copied,
        "skipped": skipped,
        "blocked": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SSID Open-Core Export")
    parser.add_argument("--target", required=True, help="Target export directory")
    parser.add_argument("--dry-run", action="store_true", help="Report without copying")
    args = parser.parse_args()

    target = Path(args.target).resolve()

    report = export(REPO_ROOT, target, dry_run=args.dry_run)

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    report["timestamp"] = ts
    report["mode"] = "dry-run" if args.dry_run else "export"

    content = json.dumps(report, indent=2)
    sha = hashlib.sha256(content.encode()).hexdigest()
    report["integrity_sha256"] = sha

    # Write evidence
    evidence_dir = REPO_ROOT / "23_compliance" / "evidence" / "ci_runs"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"{ts}_A10_opencore_export.json"
    evidence_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if report["blocked_count"] > 0:
        print(f"OPENCORE_EXPORT_WARN: {report['blocked_count']} file(s) blocked")
        for b in report["blocked"][:5]:
            print(f"  BLOCKED: {b['path']} — {b['reason']}")

    mode_str = "DRY-RUN" if args.dry_run else "EXPORTED"
    print(f"OPENCORE_EXPORT_{mode_str}: {report['copied_count']} files, {report['blocked_count']} blocked")
    print(f"  Evidence: {evidence_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
