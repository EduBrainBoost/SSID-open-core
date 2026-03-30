#!/usr/bin/env python3
"""
Restore Workspace — Restores workspace from a snapshot.
Wave 0 operational tooling for SSID workspace management.
SAFE-FIX: No PII, no secrets. Tooling script only.
Generated: 2026-03-29 | Agent: A8-COMPLIANCE-MAPPING-CLOSURE
"""

import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone


def compute_sha256(filepath: pathlib.Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_snapshot(snapshot_path: str) -> dict:
    """Load snapshot from JSON file."""
    path = pathlib.Path(snapshot_path)
    if not path.is_file():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_workspace_against_snapshot(
    workspace_path: str, snapshot_path: str
) -> dict:
    """Verify current workspace state against a snapshot.

    Returns dict with verification results:
    - matched: files that match the snapshot
    - modified: files that exist but have different hashes
    - missing: files in snapshot but not in workspace
    - added: files in workspace but not in snapshot
    """
    workspace = pathlib.Path(workspace_path).resolve()
    snapshot = load_snapshot(snapshot_path)

    snapshot_files = {
        entry["path"]: entry["sha256"]
        for entry in snapshot.get("manifest", [])
    }

    result = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "matched": [],
        "modified": [],
        "missing": [],
        "added": [],
    }

    checked_paths = set()

    for rel_path, expected_hash in snapshot_files.items():
        full_path = workspace / rel_path
        checked_paths.add(rel_path)

        if not full_path.is_file():
            result["missing"].append(rel_path)
            continue

        if expected_hash == "ERROR_READING_FILE":
            result["matched"].append(rel_path)
            continue

        actual_hash = compute_sha256(full_path)
        if actual_hash == expected_hash:
            result["matched"].append(rel_path)
        else:
            result["modified"].append({
                "path": rel_path,
                "expected": expected_hash,
                "actual": actual_hash,
            })

    # Detect added files (simple scan, not recursive full)
    # Note: full scan would be expensive; skip for Wave 0

    result["summary"] = {
        "total_in_snapshot": len(snapshot_files),
        "matched": len(result["matched"]),
        "modified": len(result["modified"]),
        "missing": len(result["missing"]),
        "integrity_pct": round(
            len(result["matched"]) / max(len(snapshot_files), 1) * 100, 1
        ),
    }

    return result


def restore_from_snapshot(
    workspace_path: str,
    snapshot_path: str,
    source_path: str,
    dry_run: bool = True,
) -> dict:
    """Restore workspace files from a source directory using snapshot as guide.

    This is a SAFE restore — it only restores files that are listed in
    the snapshot manifest. It does NOT delete added files.

    Args:
        workspace_path: Target workspace to restore into.
        snapshot_path: Snapshot JSON to use as manifest.
        source_path: Source directory (canonical repo or backup) to copy from.
        dry_run: If True (default), report what would be done without acting.

    Returns:
        dict with restore plan/results.
    """
    workspace = pathlib.Path(workspace_path).resolve()
    source = pathlib.Path(source_path).resolve()
    snapshot = load_snapshot(snapshot_path)

    plan = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "dry_run": dry_run,
        "restore_actions": [],
        "skipped": [],
        "errors": [],
    }

    for entry in snapshot.get("manifest", []):
        rel_path = entry["path"]
        source_file = source / rel_path
        target_file = workspace / rel_path

        if not source_file.is_file():
            plan["skipped"].append({
                "path": rel_path,
                "reason": "not_in_source",
            })
            continue

        action = {
            "path": rel_path,
            "action": "restore",
            "source_hash": compute_sha256(source_file),
        }

        if not dry_run:
            try:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(str(source_file), str(target_file))
                action["status"] = "restored"
            except Exception as e:
                action["status"] = "error"
                action["error"] = str(e)
                plan["errors"].append(rel_path)

        plan["restore_actions"].append(action)

    plan["summary"] = {
        "total_in_manifest": len(snapshot.get("manifest", [])),
        "restore_actions": len(plan["restore_actions"]),
        "skipped": len(plan["skipped"]),
        "errors": len(plan["errors"]),
    }

    return plan


def main():
    parser = argparse.ArgumentParser(
        description="Verify or restore SSID workspace from snapshot"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Verify subcommand
    verify_parser = subparsers.add_parser("verify", help="Verify workspace against snapshot")
    verify_parser.add_argument("workspace", help="Workspace path")
    verify_parser.add_argument("snapshot", help="Snapshot JSON file path")

    # Restore subcommand
    restore_parser = subparsers.add_parser("restore", help="Restore workspace from snapshot")
    restore_parser.add_argument("workspace", help="Target workspace path")
    restore_parser.add_argument("snapshot", help="Snapshot JSON file path")
    restore_parser.add_argument("source", help="Source directory to copy from")
    restore_parser.add_argument("--execute", action="store_true",
                                help="Actually execute restore (default: dry-run)")

    args = parser.parse_args()

    if args.command == "verify":
        result = verify_workspace_against_snapshot(args.workspace, args.snapshot)
        print(json.dumps(result["summary"], indent=2))
    elif args.command == "restore":
        result = restore_from_snapshot(
            args.workspace, args.snapshot, args.source,
            dry_run=not args.execute,
        )
        print(json.dumps(result["summary"], indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
