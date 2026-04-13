#!/usr/bin/env python3
"""Duplicate Identity Hash Detector for SSID.

Scans DID-based identity hashes across the repository to detect
collisions or duplicate registrations that could indicate gaming
of the identity system.

Detection strategies:
  - SHA3-256 hash collision detection across identity registries
  - Duplicate DID document references across roots
  - Identical identity score inputs mapped to different DIDs
"""

from __future__ import annotations

import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Patterns that indicate identity hash references
HASH_PATTERN = re.compile(r"[a-f0-9]{64}")
DID_PATTERN = re.compile(r"did:ssid:[a-zA-Z0-9._%-]+")


def scan_identity_hashes(root: Path) -> dict[str, list[str]]:
    """Scan for SHA3-256 identity hashes and track their locations.

    Returns a mapping of hash -> list of file paths where it appears.
    """
    hash_locations: dict[str, list[str]] = defaultdict(list)

    identity_dirs = [
        root / "08_identity_score",
        root / "09_meta_identity",
        root / "14_zero_time_auth",
    ]

    for identity_dir in identity_dirs:
        if not identity_dir.is_dir():
            continue
        for fpath in identity_dir.rglob("*"):
            if fpath.is_dir() or "__pycache__" in str(fpath):
                continue
            if fpath.suffix not in (".py", ".json", ".yaml", ".yml", ".md"):
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in HASH_PATTERN.finditer(content):
                h = match.group()
                rel = str(fpath.relative_to(root))
                if rel not in hash_locations[h]:
                    hash_locations[h].append(rel)

    return dict(hash_locations)


def scan_did_references(root: Path) -> dict[str, list[str]]:
    """Scan for DID references and track their locations.

    Returns a mapping of DID -> list of file paths where it appears.
    """
    did_locations: dict[str, list[str]] = defaultdict(list)

    for fpath in root.rglob("*.py"):
        if "__pycache__" in str(fpath) or ".venv" in str(fpath):
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in DID_PATTERN.finditer(content):
            did = match.group()
            rel = str(fpath.relative_to(root))
            if rel not in did_locations[did]:
                did_locations[did].append(rel)

    for fpath in root.rglob("*.json"):
        if "__pycache__" in str(fpath) or ".venv" in str(fpath):
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in DID_PATTERN.finditer(content):
            did = match.group()
            rel = str(fpath.relative_to(root))
            if rel not in did_locations[did]:
                did_locations[did].append(rel)

    return dict(did_locations)


def detect_duplicates(
    hash_locations: dict[str, list[str]],
    did_locations: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Detect duplicate identity hashes and DIDs.

    A duplicate is a hash or DID appearing in multiple identity-related
    files across different roots, which could indicate identity cloning.
    """
    findings: list[dict[str, Any]] = []

    for h, locations in hash_locations.items():
        roots_involved = set()
        for loc in locations:
            parts = loc.split("/")
            if parts:
                roots_involved.add(parts[0])

        if len(roots_involved) > 1:
            findings.append(
                {
                    "type": "cross_root_hash_duplicate",
                    "hash": h,
                    "roots": sorted(roots_involved),
                    "locations": locations,
                    "severity": "high",
                }
            )

    for did, locations in did_locations.items():
        if len(locations) > 3:
            findings.append(
                {
                    "type": "excessive_did_reference",
                    "did": did,
                    "count": len(locations),
                    "locations": locations[:10],
                    "severity": "medium",
                }
            )

    return findings


def validate(identity_data: list[dict[str, Any]] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Run duplicate identity hash validation.

    Args:
        identity_data: Optional pre-loaded identity records for testing.
        root: Repository root path. Defaults to auto-detected REPO_ROOT.

    Returns:
        Structured result with status, findings, and counts.
    """
    scan_root = root or REPO_ROOT

    if identity_data is not None:
        seen: dict[str, list[int]] = defaultdict(list)
        findings = []
        for idx, record in enumerate(identity_data):
            h = record.get("identity_hash", "")
            if h:
                seen[h].append(idx)
        for h, indices in seen.items():
            if len(indices) > 1:
                findings.append(
                    {
                        "type": "duplicate_identity_hash",
                        "hash": h,
                        "indices": indices,
                        "severity": "critical",
                    }
                )
        return {
            "status": "FAIL" if findings else "PASS",
            "check": "detect_duplicate_identity_hashes",
            "total_records": len(identity_data),
            "duplicates_found": len(findings),
            "findings": findings,
        }

    hash_locations = scan_identity_hashes(scan_root)
    did_locations = scan_did_references(scan_root)
    findings = detect_duplicates(hash_locations, did_locations)

    return {
        "status": "FAIL" if findings else "PASS",
        "check": "detect_duplicate_identity_hashes",
        "unique_hashes_scanned": len(hash_locations),
        "unique_dids_scanned": len(did_locations),
        "duplicates_found": len(findings),
        "findings": findings,
    }


def main() -> int:
    """Run duplicate identity hash detection and report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    result = validate()

    if result["duplicates_found"] > 0:
        log.warning(
            "DUPLICATE_IDENTITY_WARN: %d duplicate(s) found",
            result["duplicates_found"],
        )
        for f in result["findings"][:10]:
            log.warning("  %s: %s", f["type"], f.get("hash", f.get("did", "?")))
    else:
        log.info(
            "DUPLICATE_IDENTITY_PASS: No duplicates found (%d hashes, %d DIDs scanned)",
            result.get("unique_hashes_scanned", 0),
            result.get("unique_dids_scanned", 0),
        )

    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
