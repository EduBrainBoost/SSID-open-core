#!/usr/bin/env python3
"""
Cross-repo proof snapshot generator.

Generates hash-only proof of SSID state for interfederation verification.
Output: JSON with commit SHA + allowlisted file hashes.
Evidence written to SSID_EVIDENCE/interfed/ (external, not in repo).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ALLOWLISTED_PATHS = [
    "23_compliance/policies/sot/sot_policy.rego",
    "23_compliance/registry",
    "24_meta_orchestration/registry/sot_registry.json",
    "24_meta_orchestration/registry/shards_registry.json",
    "12_tooling/cli/run_all_gates.py",
    "12_tooling/cli/sot_validator.py",
]


def _git_head_sha(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def _hash_file(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_dir(dirpath: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not dirpath.exists():
        return result
    for f in sorted(dirpath.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
            result[rel] = _hash_file(f)
    return result


def generate_proof(repo_root: Path) -> dict:
    file_hashes: dict[str, str] = {}
    for rel_path in ALLOWLISTED_PATHS:
        full = repo_root / rel_path
        if full.is_dir():
            file_hashes.update(_hash_dir(full))
        elif full.is_file():
            file_hashes[rel_path] = _hash_file(full)
        else:
            file_hashes[rel_path] = "NOT_FOUND"

    return {
        "ssid_commit": _git_head_sha(repo_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_hashes": dict(sorted(file_hashes.items())),
        "hash_algorithm": "sha256",
        "status": "SINGLE_SYSTEM_ONLY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cross-repo proof snapshot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate but don't write to evidence",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON to stdout"
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=None,
        help="Evidence output directory",
    )
    args = parser.parse_args()

    proof = generate_proof(PROJECT_ROOT)

    if args.json or args.dry_run:
        print(json.dumps(proof, indent=2, ensure_ascii=False))

    if not args.dry_run and args.evidence_root:
        out_dir = args.evidence_root / "interfed"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_file = out_dir / f"proof_{ts}.json"
        out_file.write_text(
            json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(out_file.read_bytes()).hexdigest()
        out_file.with_suffix(".json.sha256").write_text(
            f"{digest}  {out_file.name}\n",
            encoding="utf-8",
        )
        print(f"PASS: Proof written to {out_file}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
