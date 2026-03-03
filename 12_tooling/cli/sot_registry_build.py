#!/usr/bin/env python3
"""
SoT Registry Builder — generates sot_registry.json from strict allowlist.
Deterministic: hash-only (SHA256), fixed artifact set, sorted output.
Default: READ-ONLY (print only). Use --write to persist.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "24_meta_orchestration" / "registry" / "sot_registry.json"

# Strict allowlist: exactly these 10 artifacts, no wildcards.
SOT_ALLOWLIST: list[dict[str, str]] = [
    {"name": "sot_validator_core", "path": "03_core/validators/sot/sot_validator_core.py"},
    {"name": "sot_policy_rego", "path": "23_compliance/policies/sot/sot_policy.rego"},
    {"name": "sot_contract_yaml", "path": "16_codex/contracts/sot/sot_contract.yaml"},
    {"name": "sot_validator_cli", "path": "12_tooling/cli/sot_validator.py"},
    {"name": "sot_tests", "path": "11_test_simulation/tests_compliance/test_sot_validator.py"},
    {"name": "sot_audit_report", "path": "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md"},
    {"name": "sot_diff_alert", "path": "02_audit_logging/reports/SOT_DIFF_ALERT.json"},
    {"name": "gate_runner", "path": "12_tooling/cli/run_all_gates.py"},
    {"name": "structure_spec", "path": "24_meta_orchestration/registry/structure_spec.json"},
    {"name": "sot_diff_alert_generator", "path": "12_tooling/cli/sot_diff_alert.py"},
]


def sha256_file(filepath: Path) -> str | None:
    """Calculate SHA256 hex digest of a file. Returns None if missing."""
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def build_registry() -> dict:
    """Build registry dict from allowlist. Raises if any file missing."""
    artifacts = []
    missing = []

    for entry in SOT_ALLOWLIST:
        fpath = REPO_ROOT / entry["path"]
        h = sha256_file(fpath)
        if h is None:
            missing.append(entry["path"])
        else:
            artifacts.append({
                "name": entry["name"],
                "path": entry["path"],
                "hash_sha256": h,
            })

    if missing:
        for m in missing:
            print(f"ERROR: Missing artifact: {m}")
        print(f"FAIL: {len(missing)} artifact(s) not found")
        sys.exit(1)

    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "roots": {
            "sot_artifacts": sorted(artifacts, key=lambda a: a["name"]),
        },
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="SoT Registry Builder (strict allowlist, hash-only)")
    parser.add_argument("--write", action="store_true", help="Write sot_registry.json (default: read-only)")
    parser.add_argument("--verify", action="store_true", help="Verify existing registry matches current hashes")
    args = parser.parse_args()

    registry = build_registry()

    if args.verify:
        if not REGISTRY_PATH.exists():
            print(f"FAIL: Registry not found at {REGISTRY_PATH}")
            return 1
        existing = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        existing_map = {a["name"]: a["hash_sha256"] for a in existing["roots"]["sot_artifacts"]}
        new_map = {a["name"]: a["hash_sha256"] for a in registry["roots"]["sot_artifacts"]}
        mismatches = []
        for name in sorted(set(existing_map) | set(new_map)):
            old_h = existing_map.get(name)
            new_h = new_map.get(name)
            if old_h != new_h:
                mismatches.append({"name": name, "registry": old_h, "current": new_h})
        if mismatches:
            for m in mismatches:
                print(f"MISMATCH: {m['name']} registry={m['registry']} current={m['current']}")
            return 1
        print(f"VERIFIED: {len(new_map)} artifacts match registry")
        return 0

    if args.write:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(
            json.dumps(registry, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        print(f"WRITTEN: {REGISTRY_PATH} ({len(registry['roots']['sot_artifacts'])} artifacts)")
        return 0

    # Default: read-only, print to stdout
    print(json.dumps(registry, indent=2, sort_keys=False))
    print(f"\nINFO: {len(registry['roots']['sot_artifacts'])} artifacts (read-only mode, use --write to persist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
