#!/usr/bin/env python3
"""
Promote to Canonical — Dry-run promotion of verified workspace changes.
Wave 0 operational tooling for SSID workspace management.
SAFE-FIX: No PII, no secrets. Tooling script only.
Generated: 2026-03-29 | Agent: A8-COMPLIANCE-MAPPING-CLOSURE

IMPORTANT: This script is DRY-RUN ONLY. It generates a promotion plan
but does NOT push to the canonical repository. Actual promotion requires
manual review and approval per the RFC process.
"""

import argparse
import hashlib
import json
import os
import pathlib
import sys
from datetime import datetime, timezone


# Import canonical roots from 03_core/constants.py (Single Source of Truth)
import importlib.util as _ilu
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = _ilu.spec_from_file_location("core_constants", _REPO_ROOT / "03_core" / "constants.py")
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CANONICAL_ROOTS = _mod.CANONICAL_ROOTS  # frozenset — set-compatible

EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules",
    ".pytest_cache", ".ssid-system",
}

EXCLUDED_FILES = {
    ".env", "credentials.json", ".env.local", "secrets.yaml",
}


def compute_sha256(filepath: pathlib.Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def is_within_canonical_root(rel_path: str) -> bool:
    """Check if a relative path is within a canonical root."""
    parts = pathlib.PurePosixPath(rel_path).parts
    if not parts:
        return False
    return parts[0] in CANONICAL_ROOTS


def is_excluded_file(filepath: pathlib.Path) -> bool:
    """Check if file should be excluded from promotion."""
    return filepath.name in EXCLUDED_FILES


def diff_workspace_against_canonical(
    workspace_path: str, canonical_path: str
) -> dict:
    """Compute diff between workspace and canonical repo.

    Returns dict with:
    - new_files: files in workspace not in canonical
    - modified_files: files that differ between workspace and canonical
    - promotion_eligible: files that pass all promotion checks
    - promotion_blocked: files that fail checks
    """
    workspace = pathlib.Path(workspace_path).resolve()
    canonical = pathlib.Path(canonical_path).resolve()

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "canonical": str(canonical),
        "new_files": [],
        "modified_files": [],
        "unchanged_files": [],
        "promotion_eligible": [],
        "promotion_blocked": [],
    }

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for fname in sorted(files):
            fpath = pathlib.Path(root) / fname
            rel_path = str(fpath.relative_to(workspace)).replace("\\", "/")

            # Check canonical root membership
            if not is_within_canonical_root(rel_path):
                continue

            # Check excluded files
            if is_excluded_file(fpath):
                result["promotion_blocked"].append({
                    "path": rel_path,
                    "reason": "excluded_file",
                })
                continue

            canonical_file = canonical / rel_path
            workspace_hash = compute_sha256(fpath)

            if not canonical_file.is_file():
                entry = {
                    "path": rel_path,
                    "type": "new",
                    "workspace_sha256": workspace_hash,
                }
                result["new_files"].append(entry)
                result["promotion_eligible"].append(entry)
            else:
                canonical_hash = compute_sha256(canonical_file)
                if workspace_hash != canonical_hash:
                    entry = {
                        "path": rel_path,
                        "type": "modified",
                        "workspace_sha256": workspace_hash,
                        "canonical_sha256": canonical_hash,
                    }
                    result["modified_files"].append(entry)
                    result["promotion_eligible"].append(entry)
                else:
                    result["unchanged_files"].append(rel_path)

    result["summary"] = {
        "new_files": len(result["new_files"]),
        "modified_files": len(result["modified_files"]),
        "unchanged_files": len(result["unchanged_files"]),
        "promotion_eligible": len(result["promotion_eligible"]),
        "promotion_blocked": len(result["promotion_blocked"]),
    }

    return result


def generate_promotion_plan(
    workspace_path: str, canonical_path: str, output_path: str = None
) -> dict:
    """Generate a dry-run promotion plan.

    This does NOT execute any changes. It produces a plan document
    that must be reviewed and approved before actual promotion.
    """
    diff = diff_workspace_against_canonical(workspace_path, canonical_path)

    plan = {
        "plan_id": f"PROMOTE_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "mode": "DRY_RUN_ONLY",
        "warning": "This plan does NOT execute changes. Manual review required.",
        "diff_summary": diff["summary"],
        "eligible_files": diff["promotion_eligible"],
        "blocked_files": diff["promotion_blocked"],
        "approval_required": True,
        "approval_status": "pending",
    }

    if output_path:
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
        plan["output_file"] = str(out)

    return plan


def main():
    parser = argparse.ArgumentParser(
        description="Generate dry-run promotion plan for SSID workspace changes"
    )
    parser.add_argument(
        "workspace",
        help="Path to workspace (source of changes)",
    )
    parser.add_argument(
        "canonical",
        help="Path to canonical repo (read-only target)",
    )
    parser.add_argument(
        "--output",
        help="Path to write promotion plan JSON",
    )
    args = parser.parse_args()

    try:
        plan = generate_promotion_plan(
            args.workspace, args.canonical, args.output
        )
        print(json.dumps({
            "plan_id": plan["plan_id"],
            "mode": plan["mode"],
            "eligible": plan["diff_summary"]["promotion_eligible"],
            "blocked": plan["diff_summary"]["promotion_blocked"],
            "output_file": plan.get("output_file", "STDOUT"),
        }, indent=2))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
