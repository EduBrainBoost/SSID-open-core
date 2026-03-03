#!/usr/bin/env python3
"""
Shards Registry Builder — scans all shard directories, generates shards_registry.json.
Deterministic: hash-only (SHA256), stable sort by (root_id, shard_id).

Output: 24_meta_orchestration/registry/shards_registry.json
Exit codes: 0=success, 1=verify mismatch, 2=error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.shards import find_roots, find_shards, parse_yaml, ROOTS_24

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "24_meta_orchestration" / "registry" / "shards_registry.json"

PILOT_SHARDS: set[str] = {
    "03_core/01_identitaet_personen",
    "03_core/02_dokumente_nachweise",
}


def sha256_file(filepath: Path) -> str | None:
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def get_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def scan_shard(root_name: str, shard_dir: Path) -> dict:
    shard_name = shard_dir.name
    shard_key = f"{root_name}/{shard_name}"

    chart_path = shard_dir / "chart.yaml"
    manifest_path = shard_dir / "manifest.yaml"
    contracts_index = shard_dir / "contracts" / "index.yaml"
    conformance_index = shard_dir / "conformance" / "index.yaml"
    evidence_index = shard_dir / "evidence" / "index.yaml"

    tier = "MUST" if shard_key in PILOT_SHARDS else "WARN"

    ci_path = f"{root_name}/shards/{shard_name}/contracts/index.yaml"

    entry: dict = {
        "root_id": root_name,
        "shard_id": shard_name,
        "chart_path": f"{root_name}/shards/{shard_name}/chart.yaml",
        "manifest_path": f"{root_name}/shards/{shard_name}/manifest.yaml",
        "contracts_index_path": ci_path if contracts_index.exists() else None,
        "conformance_index_path": (
            f"{root_name}/shards/{shard_name}/conformance/index.yaml"
            if conformance_index.exists()
            else None
        ),
        "evidence_index_path": (
            f"{root_name}/shards/{shard_name}/evidence/index.yaml"
            if evidence_index.exists()
            else None
        ),
        "sha256": {
            "chart": sha256_file(chart_path),
            "manifest": sha256_file(manifest_path),
            "contracts_index": sha256_file(contracts_index),
            "conformance_index": sha256_file(conformance_index),
            "evidence_index": sha256_file(evidence_index),
        },
        "entrypoints": [],
        "promotion_tier": tier,
    }

    if contracts_index.exists():
        entry["entrypoints"].append({
            "kind": "contract_validate",
            "target": ci_path,
        })

    return entry


def build_registry(roots: list[Path], deterministic: bool) -> dict:
    shards = []
    for root_path in roots:
        root_name = root_path.name
        for shard_dir in find_shards(root_path):
            entry = scan_shard(root_name, shard_dir)
            shards.append(entry)

    shards.sort(key=lambda s: (s["root_id"], s["shard_id"]))

    registry: dict = {
        "schema_version": "1.0.0",
        "git_sha": get_git_sha(),
        "shard_count": len(shards),
        "shards": shards,
    }

    if not deterministic:
        from datetime import datetime, timezone
        registry["generated_at_utc"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    return registry


def verify_registry(registry: dict) -> tuple[bool, list[str]]:
    if not REGISTRY_PATH.exists():
        return False, ["shards_registry.json does not exist"]

    existing = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    diffs = []

    existing_map = {
        (s["root_id"], s["shard_id"]): s for s in existing.get("shards", [])
    }
    new_map = {(s["root_id"], s["shard_id"]): s for s in registry.get("shards", [])}

    for key in sorted(set(existing_map.keys()) | set(new_map.keys())):
        if key not in existing_map:
            diffs.append(f"NEW shard: {key[0]}/{key[1]}")
            continue
        if key not in new_map:
            diffs.append(f"REMOVED shard: {key[0]}/{key[1]}")
            continue
        old_h, new_h = existing_map[key].get("sha256", {}), new_map[key].get("sha256", {})
        for field in ["chart", "manifest", "contracts_index", "conformance_index", "evidence_index"]:
            if old_h.get(field) != new_h.get(field):
                diffs.append(
                    f"HASH MISMATCH: {key[0]}/{key[1]}.{field}: "
                    f"{old_h.get(field)} -> {new_h.get(field)}"
                )

    # git_sha drift is expected after any commit (circular dependency);
    # report as INFO, not as integrity failure.
    if existing.get("git_sha") != registry.get("git_sha"):
        print(
            f"INFO: git_sha drift (expected): "
            f"{existing.get('git_sha')[:12]}... -> {registry.get('git_sha')[:12]}..."
        )

    return len(diffs) == 0, diffs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Shards Registry Builder (hash-only, stable sort, deterministic)"
    )
    parser.add_argument("--source", choices=["local-run", "ci-run"], default="local-run")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=str, default=str(REGISTRY_PATH))
    args = parser.parse_args()

    roots = find_roots(REPO_ROOT)
    registry = build_registry(roots, args.deterministic)

    if args.verify:
        ok, diffs = verify_registry(registry)
        if ok:
            print("PASS: shards_registry.json matches computed state")
            return 0
        print("FAIL: shards_registry.json drift detected")
        for d in diffs:
            print(f"  {d}")
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(registry, indent=2, ensure_ascii=False) + "\n"
    out.write_text(content, encoding="utf-8")
    print(f"WRITTEN: {out}")

    must = sum(1 for s in registry["shards"] if s["promotion_tier"] == "MUST")
    print(f"Summary: {registry['shard_count']} shards ({must} MUST, {registry['shard_count'] - must} WARN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
