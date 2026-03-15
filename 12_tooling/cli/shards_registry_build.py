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
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.shards import find_roots, find_shards, parse_yaml, ROOTS_24

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "24_meta_orchestration" / "registry" / "shards_registry.json"
REPORTS_DIR = REPO_ROOT / "02_audit_logging" / "reports"

PILOT_SHARDS: set[str] = {
    "03_core/01_identitaet_personen",
    "03_core/02_dokumente_nachweise",
}

ROOT03_RUNTIME_SHARDS: set[str] = {
    "03_core/01_identitaet_personen",
    "03_core/02_dokumente_nachweise",
    "03_core/03_shard_03",
    "03_core/04_shard_04",
    "03_core/05_shard_05",
}

ROOT09_RUNTIME_SHARDS: set[str] = {
    "09_meta_identity/01_identitaet_personen",
    "09_meta_identity/02_dokumente_nachweise",
    "09_meta_identity/03_shard_03",
    "09_meta_identity/04_shard_04",
    "09_meta_identity/05_shard_05",
}

ROOT07_RUNTIME_SHARDS: set[str] = {
    "07_governance_legal/01_identitaet_personen",
    "07_governance_legal/02_dokumente_nachweise",
    "07_governance_legal/03_shard_03",
    "07_governance_legal/04_shard_04",
    "07_governance_legal/05_shard_05",
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


def scan_shard(root_name: str, shard_dir: Path, *, repo_root: Path, deterministic: bool = False) -> dict:
    shard_name = shard_dir.name
    shard_key = f"{root_name}/{shard_name}"

    chart_path = shard_dir / "chart.yaml"
    manifest_path = shard_dir / "manifest.yaml"
    contracts_index = shard_dir / "contracts" / "index.yaml"
    conformance_index = shard_dir / "conformance" / "index.yaml"
    evidence_index = shard_dir / "evidence" / "index.yaml"
    runtime_index = shard_dir / "runtime" / "index.yaml"
    readme_path = shard_dir / "README.md"
    contracts_dir = shard_dir / "contracts"
    fixtures_dir = shard_dir / "conformance" / "fixtures"

    contract_status = "missing"
    if contracts_dir.is_dir() and all((contracts_dir / name).exists() for name in ["inputs.schema.json", "outputs.schema.json", "events.schema.json"]):
        contract_status = "ready"

    conformance_status = "missing"
    if fixtures_dir.is_dir() and (fixtures_dir / "fixture_valid.json").exists() and (fixtures_dir / "fixture_invalid.json").exists():
        conformance_status = "ready"

    evidence_status = "ready" if evidence_index.exists() else "missing"
    runtime_status = "ready" if runtime_index.exists() else "missing"
    service_runtime_status = "ready" if root_name == "09_meta_identity" and runtime_status == "ready" else "not_applicable"
    security_status = "ready" if root_name == "07_governance_legal" and runtime_status == "ready" else "not_applicable"
    runtime_dependency_refs: list[str] = []
    dependency_status = "not_applicable"
    if runtime_index.exists():
        runtime_spec = parse_yaml(runtime_index) or {}
        runtime_dependency_refs = list(runtime_spec.get("dependency_refs", []) or [])
        dependency_status = "ready"
        for dependency_ref in runtime_dependency_refs:
            dep_root, dep_shard = str(dependency_ref).split("/", 1)
            dep_runtime = repo_root / dep_root / "shards" / dep_shard / "runtime" / "index.yaml"
            if not dep_runtime.is_file():
                dependency_status = "missing"
                break
    status = "scaffold"
    verification_result = "WARN"
    if chart_path.exists() and manifest_path.exists():
        status = "defined"
    if contract_status == "ready":
        status = "contract_ready"
    if contract_status == "ready" and conformance_status == "ready" and evidence_status == "ready" and readme_path.exists():
        status = "conformance_ready"
        verification_result = "PASS"
    if shard_key in ROOT03_RUNTIME_SHARDS and runtime_status == "ready" and verification_result == "PASS":
        status = "runtime_ready"
    if shard_key in ROOT09_RUNTIME_SHARDS and runtime_status == "ready" and dependency_status == "ready" and verification_result == "PASS":
        status = "cross_root_runtime_ready"
    if shard_key in ROOT07_RUNTIME_SHARDS and runtime_status == "ready" and dependency_status == "ready" and verification_result == "PASS":
        status = "security_enforced"

    tier = "MUST" if verification_result == "PASS" else "WARN"

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
        "runtime_index_path": (
            f"{root_name}/shards/{shard_name}/runtime/index.yaml"
            if runtime_index.exists()
            else None
        ),
        "sha256": {
            "chart": sha256_file(chart_path),
            "manifest": sha256_file(manifest_path),
            "contracts_index": sha256_file(contracts_index),
            "conformance_index": sha256_file(conformance_index),
            "evidence_index": sha256_file(evidence_index),
            "runtime_index": sha256_file(runtime_index),
        },
        "entrypoints": [],
        "promotion_tier": tier,
        "status": status,
        "contract_status": contract_status,
        "conformance_status": conformance_status,
        "evidence_status": evidence_status,
        "runtime_status": runtime_status,
        "service_runtime_status": service_runtime_status,
        "security_status": security_status,
        "dependency_status": dependency_status,
        "runtime_dependency_refs": runtime_dependency_refs,
        "security_enforced": shard_key in ROOT07_RUNTIME_SHARDS and security_status == "ready" and dependency_status == "ready",
        "gate_status": verification_result,
        "last_verified_at": "deterministic" if deterministic else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verification_mode": "deterministic" if deterministic else "live",
        "verification_result": verification_result,
        "warnings": [] if verification_result == "PASS" else ["verification incomplete"],
        "blocking_findings": [] if verification_result == "PASS" else ["missing shard readiness requirements"],
    }

    if contracts_index.exists():
        entry["entrypoints"].append({
            "kind": "contract_validate",
            "target": ci_path,
        })
    if runtime_index.exists():
        entry["entrypoints"].append({
            "kind": "runtime_execute",
            "target": f"{root_name}/shards/{shard_name}/runtime/index.yaml",
        })

    return entry


def build_registry(roots: list[Path], deterministic: bool) -> dict:
    shards = []
    for root_path in roots:
        root_name = root_path.name
        for shard_dir in find_shards(root_path):
            entry = scan_shard(root_name, shard_dir, repo_root=root_path.parent, deterministic=deterministic)
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
        if old_h.get("runtime_index") != new_h.get("runtime_index"):
            diffs.append(
                f"HASH MISMATCH: {key[0]}/{key[1]}.runtime_index: "
                f"{old_h.get('runtime_index')} -> {new_h.get('runtime_index')}"
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
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    coverage_payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "shard_count": registry["shard_count"],
        "contract_ready": sum(1 for s in registry["shards"] if s["contract_status"] == "ready"),
        "conformance_ready": sum(1 for s in registry["shards"] if s["conformance_status"] == "ready"),
        "gate_pass": sum(1 for s in registry["shards"] if s["gate_status"] == "PASS"),
        "runtime_ready": sum(1 for s in registry["shards"] if s.get("runtime_status") == "ready"),
        "cross_root_runtime_ready": sum(1 for s in registry["shards"] if s.get("dependency_status") == "ready"),
        "security_enforced": sum(1 for s in registry["shards"] if s.get("security_enforced") is True),
        "warn_count": sum(1 for s in registry["shards"] if s["verification_result"] != "PASS"),
    }
    (REPORTS_DIR / "SHARD_CONFORMANCE_MATRIX.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "SHARD_CONFORMANCE_MATRIX.md").write_text(
        "# Shard Conformance Matrix\n\n"
        f"- Shards: {registry['shard_count']}\n"
        f"- Gate PASS: {coverage_payload['gate_pass']}\n"
        f"- Runtime ready: {coverage_payload['runtime_ready']}\n"
        f"- Cross-root ready: {coverage_payload['cross_root_runtime_ready']}\n"
        f"- Security enforced: {coverage_payload['security_enforced']}\n"
        f"- WARN: {coverage_payload['warn_count']}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "CONTRACT_COVERAGE_REPORT.md").write_text(
        "# Contract Coverage Report\n\n"
        f"- Contract ready: {coverage_payload['contract_ready']}/{registry['shard_count']}\n"
        f"- Conformance ready: {coverage_payload['conformance_ready']}/{registry['shard_count']}\n"
        f"- Runtime ready: {coverage_payload['runtime_ready']}/{registry['shard_count']}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "REGISTRY_WARN_BREAKDOWN.md").write_text(
        "# Registry Warn Breakdown\n\n"
        f"- WARN shards: {coverage_payload['warn_count']}\n"
        f"- PASS shards: {coverage_payload['gate_pass']}\n",
        encoding="utf-8",
    )
    print(f"Summary: {registry['shard_count']} shards ({must} MUST, {registry['shard_count'] - must} WARN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
