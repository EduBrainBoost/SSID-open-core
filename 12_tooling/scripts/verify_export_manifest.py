#!/usr/bin/env python3
"""Verify export manifest — validates the structure and required fields."""
from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_FIELDS = [
    "export_id",
    "source_repo",
    "source_commit",
    "source_registry_hash",
    "target_repo",
    "target_base_commit",
    "allowlist",
    "denylist",
    "transforms",
    "license_map",
    "provenance_map",
    "source_file_hashes",
    "generated_file_hashes",
    "private_leak_scan",
    "secret_scan",
    "pii_scan",
    "license_scan",
    "verifier",
    "created_at_utc",
]


def verify_export_manifest(repo_root: Path | str = ".") -> dict:
    root = Path(repo_root)
    registry_path = root / "24_meta_orchestration" / "registry" / "opencore_export_registry.json"

    if not registry_path.exists():
        return {"valid": False, "error": "Registry file missing", "status": "FAIL"}

    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"Invalid JSON: {e}", "status": "FAIL"}

    manifests = registry.get("manifests", [])
    results = {
        "valid": True,
        "registry_exists": True,
        "manifest_count": len(manifests),
        "issues": [],
        "status": "PASS",
    }

    if len(manifests) == 0:
        results["issues"].append("No export manifests yet (expected for initial build)")

    for m in manifests:
        for field in REQUIRED_FIELDS:
            if field not in m:
                results["issues"].append(f"Manifest {m.get('export_id', '?')} missing field: {field}")
                results["valid"] = False

    return results


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    result = verify_export_manifest(repo)
    print(f"Status: {result['status']}")
    print(f"Registry exists: {result['registry_exists']}")
    print(f"Manifests: {result['manifest_count']}")
    for issue in result["issues"]:
        print(f"  - {issue}")
    sys.exit(0 if result["valid"] else 1)
