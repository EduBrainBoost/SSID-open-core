#!/usr/bin/env python3
"""AGENT 09 — Dependency Audit Script.

Checks requirements.txt / requirements.lock for known-vulnerable patterns
and generates an audit report. This is a lightweight pre-CI check, not a
replacement for full CVE scanning (which runs in CI via dependency_scan.yml).

SoT v4.1.0 | ROOT-24-LOCK | Classification: Security
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Patterns that indicate insecure dependency specifications
INSECURE_PATTERNS = [
    {"name": "unpinned_dependency", "regex": r"^[a-zA-Z][\w.-]+\s*$", "severity": "warning",
     "description": "Dependency without version pin"},
    {"name": "git_dependency", "regex": r"git\+https?://", "severity": "warning",
     "description": "Git URL dependency (not reproducible)"},
    {"name": "http_dependency", "regex": r"^https?://", "severity": "high",
     "description": "Direct HTTP URL dependency (integrity risk)"},
]

REQUIREMENTS_FILES = [
    "requirements.txt",
    "requirements.lock",
    "requirements-dev.txt",
]


def audit_file(filepath: Path) -> list[dict]:
    """Audit a single requirements file."""
    findings = []
    if not filepath.exists():
        return findings

    for lineno, line in enumerate(filepath.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue

        for pattern in INSECURE_PATTERNS:
            if re.match(pattern["regex"], stripped):
                findings.append({
                    "file": str(filepath.relative_to(REPO_ROOT)),
                    "line": lineno,
                    "content": stripped,
                    "pattern": pattern["name"],
                    "severity": pattern["severity"],
                    "description": pattern["description"],
                })

    return findings


def main() -> int:
    all_findings = []

    for req_file in REQUIREMENTS_FILES:
        filepath = REPO_ROOT / req_file
        all_findings.extend(audit_file(filepath))

    # Also check module-level requirements
    for req in REPO_ROOT.rglob("requirements.txt"):
        if any(skip in req.parts for skip in {".git", "node_modules", ".venv"}):
            continue
        all_findings.extend(audit_file(req))

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    report = {
        "gate": "dependency_audit",
        "timestamp": ts,
        "finding_count": len(all_findings),
        "status": "FAIL" if any(f["severity"] == "high" for f in all_findings) else "PASS",
        "findings": all_findings,
    }

    content = json.dumps(report, indent=2)
    report["integrity_sha256"] = hashlib.sha256(content.encode()).hexdigest()

    # Write evidence
    evidence_dir = REPO_ROOT / "23_compliance" / "evidence" / "ci_runs"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"{ts}_A09_dependency_audit.json"
    evidence_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    high_count = sum(1 for f in all_findings if f["severity"] == "high")
    warn_count = sum(1 for f in all_findings if f["severity"] == "warning")

    if high_count > 0:
        print(f"DEPENDENCY_AUDIT_FAIL: {high_count} high-severity finding(s)")
        for f in all_findings:
            if f["severity"] == "high":
                print(f"  HIGH: {f['file']}:{f['line']} — {f['description']}")
        return 1

    if warn_count > 0:
        print(f"DEPENDENCY_AUDIT_WARN: {warn_count} warning(s)")
        for f in all_findings[:5]:
            print(f"  WARN: {f['file']}:{f['line']} — {f['description']}")

    print(f"DEPENDENCY_AUDIT_PASS: Evidence at {evidence_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
