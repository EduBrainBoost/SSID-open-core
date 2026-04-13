#!/usr/bin/env python3
"""
SoT Diff Alert Generator
Generates SOT_DIFF_ALERT.json by comparing registry hashes with current file hashes.
Default: READ-ONLY (compare only, no writes).
Use --write to persist results.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(filepath):
    """Calculate SHA256 hash of a file."""
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return None


def load_registry():
    """Load SOT registry."""
    registry_path = Path("24_meta_orchestration/registry/sot_registry.json")
    if not registry_path.exists():
        print(f"ERROR: Registry not found at {registry_path}")
        sys.exit(1)

    with open(registry_path) as f:
        return json.load(f)


def generate_diff_alert(write_output=False):
    """Generate diff alert by comparing registry with current state."""
    registry = load_registry()
    artifacts = registry["roots"]["sot_artifacts"]

    changes = []
    missing = []
    mismatched_hashes = []

    for artifact in artifacts:
        name = artifact["name"]
        path = artifact["path"]
        expected_hash = artifact["hash_sha256"]

        current_hash = sha256_file(path)

        if current_hash is None:
            missing.append({"name": name, "path": path, "expected_hash": expected_hash})
        elif current_hash != expected_hash:
            mismatched_hashes.append(
                {
                    "name": name,
                    "path": path,
                    "expected_hash": expected_hash,
                    "current_hash": current_hash,
                }
            )
        else:
            changes.append({"name": name, "path": path, "status": "unchanged"})

    status = "FAIL" if (missing or mismatched_hashes) else "PASS"

    output_path = Path("02_audit_logging/reports") / "SOT_DIFF_ALERT.json"

    diff_alert = {
        "schema_version": "1.0.0",
        "status": status,
        "changes": sorted(changes, key=lambda x: (x.get("name", ""), x.get("path", ""))),
        "missing": sorted(missing, key=lambda x: (x.get("name", ""), x.get("path", ""))),
        "mismatched_hashes": sorted(mismatched_hashes, key=lambda x: (x.get("name", ""), x.get("path", ""))),
    }

    if not write_output:
        print(f"SOT Diff Alert (READ-ONLY mode): {output_path}")
        print(f"Status: {status}")
        if missing:
            print(f"Missing files: {len(missing)}")
        if mismatched_hashes:
            print(f"Mismatched hashes: {len(mismatched_hashes)}")
        return diff_alert

    # Ensure reports directory exists
    reports_dir = Path("02_audit_logging/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Write diff alert
    output_path = reports_dir / "SOT_DIFF_ALERT.json"
    with open(output_path, "w") as f:
        json.dump(diff_alert, f, indent=2)

    print(f"SOT Diff Alert generated: {output_path}")
    print(f"Status: {status}")

    if missing:
        print(f"Missing files: {len(missing)}")
    if mismatched_hashes:
        print(f"Mismatched hashes: {len(mismatched_hashes)}")

    # Exit with error code if status is FAIL
    if status == "FAIL":
        sys.exit(1)

    return diff_alert


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SOT Diff Alert Generator")
    parser.add_argument(
        "--write",
        action="store_true",
        default=False,
        help="Write output to SOT_DIFF_ALERT.json (default: READ-ONLY)",
    )
    args = parser.parse_args()
    generate_diff_alert(write_output=args.write)
