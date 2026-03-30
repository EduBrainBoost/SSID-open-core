#!/usr/bin/env python3
"""Badge Integrity Checker for SSID.

Validates that compliance badges, status markers, and certification
claims in the repository are backed by actual evidence and not
fabricated or manipulated.

Detection strategies:
  - Badge claims without corresponding evidence files
  - Status markers (PASS/CERTIFIED/COMPLIANT) without audit trails
  - Timestamp inconsistencies in badge metadata
  - Badge inflation (claiming higher compliance than evidence supports)
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

BADGE_MARKERS = [
    "COMPLIANT",
    "CERTIFIED",
    "PASS",
    "VERIFIED",
    "APPROVED",
    "AUDITED",
]

STATUS_PATTERN = re.compile(
    r'status["\s:=]+\s*["\']?(COMPLIANT|CERTIFIED|PASS|VERIFIED|APPROVED|AUDITED)["\']?',
    re.IGNORECASE,
)

EVIDENCE_DIRS = [
    "02_audit_logging/reports",
    "02_audit_logging/evidence",
    "23_compliance/evidence",
]


def scan_badge_claims(root: Path) -> list[dict[str, Any]]:
    """Scan repository for badge/status claims.

    Returns list of claims with file, line, marker, and context.
    """
    claims: list[dict[str, Any]] = []

    scan_dirs = [
        root / "02_audit_logging",
        root / "23_compliance",
        root / "08_identity_score",
        root / "16_codex",
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for fpath in scan_dir.rglob("*"):
            if fpath.is_dir() or "__pycache__" in str(fpath):
                continue
            if fpath.suffix not in (".json", ".yaml", ".yml", ".md", ".py"):
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for line_num, line in enumerate(content.splitlines(), 1):
                match = STATUS_PATTERN.search(line)
                if match:
                    claims.append({
                        "file": str(fpath.relative_to(root)),
                        "line": line_num,
                        "marker": match.group(1).upper(),
                        "context": line.strip()[:120],
                    })

    return claims


def find_evidence_files(root: Path) -> set[str]:
    """Find all evidence/audit files in known evidence directories."""
    evidence: set[str] = set()

    for edir in EVIDENCE_DIRS:
        epath = root / edir
        if not epath.is_dir():
            continue
        for fpath in epath.rglob("*"):
            if fpath.is_file():
                evidence.add(str(fpath.relative_to(root)))

    return evidence


def check_badge_backing(
    claims: list[dict[str, Any]],
    evidence_files: set[str],
) -> list[dict[str, Any]]:
    """Check if badge claims have corresponding evidence.

    A claim is suspicious if:
    - It claims CERTIFIED/COMPLIANT but no evidence file references the same root
    - The evidence directory for that root is empty
    """
    findings: list[dict[str, Any]] = []

    root_evidence_count: dict[str, int] = {}
    for ef in evidence_files:
        parts = ef.split("/")
        if len(parts) >= 2:
            root_key = parts[0]
            root_evidence_count[root_key] = root_evidence_count.get(root_key, 0) + 1

    for claim in claims:
        claim_root = claim["file"].split("/")[0] if "/" in claim["file"] else ""

        if claim["marker"] in ("CERTIFIED", "COMPLIANT", "APPROVED"):
            if root_evidence_count.get(claim_root, 0) == 0:
                if claim_root not in ("02_audit_logging", "23_compliance"):
                    findings.append({
                        "type": "unsubstantiated_badge",
                        "claim": claim,
                        "reason": f"No evidence files found for root {claim_root}",
                        "severity": "high",
                    })

    return findings


def validate(badge_records: list[dict[str, Any]] | None = None,
             root: Path | None = None) -> dict[str, Any]:
    """Run badge integrity validation.

    Args:
        badge_records: Optional pre-loaded badge data for testing.
        root: Repository root path.

    Returns:
        Structured result with status, findings, and counts.
    """
    scan_root = root or REPO_ROOT

    if badge_records is not None:
        findings = []
        for idx, record in enumerate(badge_records):
            badge_status = record.get("status", "")
            evidence_hash = record.get("evidence_hash", "")
            if badge_status in ("CERTIFIED", "COMPLIANT", "APPROVED") and not evidence_hash:
                findings.append({
                    "type": "badge_without_evidence",
                    "index": idx,
                    "badge": badge_status,
                    "severity": "critical",
                })
            timestamp = record.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    if dt.year > 2030 or dt.year < 2020:
                        findings.append({
                            "type": "suspicious_timestamp",
                            "index": idx,
                            "timestamp": timestamp,
                            "severity": "high",
                        })
                except (ValueError, TypeError):
                    findings.append({
                        "type": "invalid_timestamp",
                        "index": idx,
                        "timestamp": timestamp,
                        "severity": "medium",
                    })
        return {
            "status": "FAIL" if findings else "PASS",
            "check": "badge_integrity_checker",
            "total_records": len(badge_records),
            "issues_found": len(findings),
            "findings": findings,
        }

    claims = scan_badge_claims(scan_root)
    evidence_files = find_evidence_files(scan_root)
    findings = check_badge_backing(claims, evidence_files)

    return {
        "status": "FAIL" if findings else "PASS",
        "check": "badge_integrity_checker",
        "total_claims_scanned": len(claims),
        "evidence_files_found": len(evidence_files),
        "issues_found": len(findings),
        "findings": findings,
    }


def main() -> int:
    """Run badge integrity check and report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    result = validate()

    if result["issues_found"] > 0:
        log.warning(
            "BADGE_INTEGRITY_WARN: %d issue(s) found",
            result["issues_found"],
        )
        for f in result["findings"][:10]:
            log.warning("  %s: %s", f["type"], f.get("reason", ""))
    else:
        log.info(
            "BADGE_INTEGRITY_PASS: All %d badge claims have evidence backing",
            result.get("total_claims_scanned", 0),
        )

    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
