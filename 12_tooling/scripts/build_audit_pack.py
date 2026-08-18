#!/usr/bin/env python3
"""Build audit pack — compiles all compliance evidence into a single archive."""
from __future__ import annotations

import json
import hashlib
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_audit_pack(repo_root: Path | str = ".") -> dict:
    root = Path(repo_root)
    evidence_files = list(root.rglob("*.json"))
    policy_files = list(root.rglob("*.yaml"))

    pack = {
        "build_id": f"audit-pack-{datetime.now(timezone.utc).isoformat()}",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_files": [],
        "policy_files": [],
        "total_files": 0,
        "combined_hash": "",
    }

    for f in evidence_files:
        pack["evidence_files"].append({
            "path": str(f.relative_to(root)),
            "sha256": sha256_file(f),
            "size": f.stat().st_size,
        })

    for f in policy_files:
        pack["policy_files"].append({
            "path": str(f.relative_to(root)),
            "sha256": sha256_file(f),
            "size": f.stat().st_size,
        })

    pack["total_files"] = len(pack["evidence_files"]) + len(pack["policy_files"])

    # Combined hash of all file hashes
    all_hashes = sorted(
        [e["sha256"] for e in pack["evidence_files"]]
        + [p["sha256"] for p in pack["policy_files"]]
    )
    pack["combined_hash"] = hashlib.sha256("\n".join(all_hashes).encode()).hexdigest()

    return pack


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    pack = build_audit_pack(repo)
    print(json.dumps(pack, indent=2))
