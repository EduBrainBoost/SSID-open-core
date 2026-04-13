#!/usr/bin/env python3
"""
Snapshot Workspace — Creates timestamped snapshot of workspace state.
Wave 0 operational tooling for SSID workspace management.
SAFE-FIX: No PII, no secrets. Tooling script only.
Generated: 2026-03-29 | Agent: A8-COMPLIANCE-MAPPING-CLOSURE
"""

import argparse
import hashlib
import json
import os
import pathlib
import sys
from datetime import UTC, datetime

CLI_DIR = pathlib.Path(__file__).resolve().parents[1] / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

from _lib.canonical_paths import ensure_canonical_repo_root, ensure_canonical_write_path


def compute_sha256(filepath: pathlib.Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_file_manifest(workspace: pathlib.Path, exclude_dirs: set) -> list:
    """Collect file manifest with hashes for all tracked files."""
    manifest = []
    for root, dirs, files in os.walk(workspace):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in sorted(files):
            fpath = pathlib.Path(root) / fname
            rel_path = fpath.relative_to(workspace)
            try:
                sha256 = compute_sha256(fpath)
                size = fpath.stat().st_size
                manifest.append(
                    {
                        "path": str(rel_path),
                        "sha256": sha256,
                        "size": size,
                    }
                )
            except (OSError, PermissionError):
                manifest.append(
                    {
                        "path": str(rel_path),
                        "sha256": "ERROR_READING_FILE",
                        "size": -1,
                    }
                )
    return manifest


def create_snapshot(workspace_path: str, output_dir: str = None, dry_run: bool = False) -> dict:
    """Create a timestamped snapshot of workspace state.

    Args:
        workspace_path: Path to workspace root.
        output_dir: Directory to write snapshot. Defaults to
            workspace/.ssid-system/snapshots/.
        dry_run: If True, compute manifest but do not write files.

    Returns:
        dict with snapshot metadata.
    """
    workspace = ensure_canonical_repo_root(workspace_path, repo_root=pathlib.Path(__file__).resolve().parents[2])
    if not workspace.is_dir():
        raise FileNotFoundError(f"Workspace not found: {workspace}")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"SNAPSHOT_{timestamp}"

    exclude_dirs = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".ssid-system",
    }

    manifest = collect_file_manifest(workspace, exclude_dirs)

    snapshot_meta = {
        "snapshot_id": snapshot_id,
        "timestamp": timestamp,
        "workspace_path": str(workspace),
        "total_files": len(manifest),
        "manifest": manifest,
    }

    if dry_run:
        snapshot_meta["dry_run"] = True
        return snapshot_meta

    output_base = workspace / ".ssid-system" / "snapshots" if output_dir is None else pathlib.Path(output_dir)

    output_base = ensure_canonical_write_path(output_base, repo_root=workspace)

    output_base.mkdir(parents=True, exist_ok=True)
    snapshot_file = output_base / f"{snapshot_id}.json"

    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(snapshot_meta, f, indent=2)

    snapshot_meta["snapshot_file"] = str(snapshot_file)
    return snapshot_meta


def main():
    parser = argparse.ArgumentParser(description="Create timestamped snapshot of SSID workspace state")
    parser.add_argument(
        "workspace",
        help="Path to workspace root",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for snapshot (default: workspace/.ssid-system/snapshots/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute manifest without writing snapshot file",
    )
    args = parser.parse_args()

    try:
        result = create_snapshot(
            args.workspace,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
        print(
            json.dumps(
                {
                    "snapshot_id": result["snapshot_id"],
                    "total_files": result["total_files"],
                    "snapshot_file": result.get("snapshot_file", "DRY_RUN"),
                    "dry_run": result.get("dry_run", False),
                },
                indent=2,
            )
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
