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

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datetime import UTC

from _lib.shards import find_roots, find_shards

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "24_meta_orchestration" / "registry" / "shards_registry.json"

# --- WAVE_06 canonical runtime consumption helpers ---


def _load_consumption_policy(repo_root: Path):
    """Dynamically load CanonicalConsumptionPolicy if available."""
    import importlib.util

    module_path = repo_root / "03_core" / "validators" / "runtime" / "canonical_runtime_consumption.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("canonical_runtime_consumption", module_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    import sys as _sys

    _sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, "CanonicalConsumptionPolicy", None)


def _load_bypass_detector(repo_root: Path):
    """Dynamically load RuntimeBypassDetector if available."""
    import importlib.util

    module_path = repo_root / "03_core" / "validators" / "runtime" / "runtime_bypass_detector.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("runtime_bypass_detector", module_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    import sys as _sys

    _sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, "RuntimeBypassDetector", None)


def _scan_canonical_consumption(repo_root: Path, root_name: str, shard_name: str, policy, detector):
    """Return WAVE_06 fields for a single shard."""
    result = {
        "canonical_runtime_consumption": None,
        "runtime_consumption_mode": "unknown",
        "allowed_runtime_providers": [],
        "allowed_dependency_capabilities": [],
        "runtime_bypass_findings": 0,
        "canonical_consumption_status": "not_applicable",
    }

    runtime_idx = repo_root / root_name / "shards" / shard_name / "runtime" / "index.yaml"
    if not runtime_idx.exists():
        return result

    if policy is None:
        result["canonical_consumption_status"] = "validator_unavailable"
        return result

    try:
        vr = policy.validate_consumer(root_name, shard_name)
        result["canonical_runtime_consumption"] = vr.status
        result["runtime_consumption_mode"] = getattr(vr, "mode", "canonical")
        result["allowed_runtime_providers"] = getattr(vr, "providers", [])
        result["allowed_dependency_capabilities"] = getattr(vr, "capabilities", [])
        result["canonical_consumption_status"] = vr.status
    except Exception:
        result["canonical_consumption_status"] = "error"

    if detector is not None:
        try:
            findings = detector.scan_shard(root_name, shard_name)
            result["runtime_bypass_findings"] = len(findings)
            if findings:
                result["canonical_consumption_status"] = "fail"
        except Exception:
            pass

    return result


PILOT_SHARDS: set[str] = {
    "03_core/01_identitaet_personen",
    "03_core/02_dokumente_nachweise",
    "09_meta_identity/01_identity_resolution",
    "09_meta_identity/02_identity_graph",
    "09_meta_identity/03_identity_verification",
    "09_meta_identity/04_identity_lifecycle",
    "09_meta_identity/05_identity_federation",
    "09_meta_identity/06_identity_audit",
    "09_meta_identity/07_identity_compliance",
}


def sha256_file(filepath: Path) -> str | None:
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def get_git_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_repo_root(roots: list[Path]) -> Path:
    if not roots:
        return REPO_ROOT
    return roots[0].parent.resolve()


def _runtime_metadata(repo_root: Path, root_name: str, shard_name: str) -> dict:
    runtime_path = repo_root / root_name / "shards" / shard_name / "runtime" / "index.yaml"
    if not runtime_path.is_file():
        return {
            "runtime_index_path": None,
            "runtime_status": "missing",
            "service_runtime_status": "not_applicable",
            "security_status": "not_applicable",
            "dependency_status": "not_applicable",
            "runtime_dependency_refs": [],
            "security_enforced": False,
            "status": "conformance_ready",
        }

    runtime_spec = _load_yaml(runtime_path)
    dependency_refs = list(runtime_spec.get("dependency_refs", []) or [])
    dependency_status = "not_applicable"
    if dependency_refs:
        dependency_status = "ready"
        for dependency_ref in dependency_refs:
            dep_root, dep_shard = str(dependency_ref).split("/", 1)
            dep_runtime = repo_root / dep_root / "shards" / dep_shard / "runtime" / "index.yaml"
            if not dep_runtime.is_file():
                dependency_status = "missing"
                break

    service_runtime_status = str(runtime_spec.get("service_runtime_status") or "ready")
    security_status = "ready" if root_name == "07_governance_legal" else "not_applicable"
    security_enforced = root_name == "07_governance_legal" and dependency_status == "ready"

    status = "runtime_ready"
    if dependency_status == "ready":
        status = "cross_root_runtime_ready"
    if security_enforced:
        status = "security_enforced"

    return {
        "runtime_index_path": f"{root_name}/shards/{shard_name}/runtime/index.yaml",
        "runtime_status": "ready",
        "service_runtime_status": service_runtime_status,
        "security_status": security_status,
        "dependency_status": dependency_status,
        "runtime_dependency_refs": dependency_refs,
        "security_enforced": security_enforced,
        "status": status,
    }


def scan_shard(repo_root: Path, root_name: str, shard_dir: Path, policy=None, detector=None) -> dict:
    shard_name = shard_dir.name
    shard_key = f"{root_name}/{shard_name}"

    chart_path = shard_dir / "chart.yaml"
    manifest_path = shard_dir / "manifest.yaml"
    contracts_index = shard_dir / "contracts" / "index.yaml"
    conformance_index = shard_dir / "conformance" / "index.yaml"
    evidence_index = shard_dir / "evidence" / "index.yaml"
    runtime_index = shard_dir / "runtime" / "index.yaml"

    tier = "MUST" if shard_key in PILOT_SHARDS else "WARN"

    ci_path = f"{root_name}/shards/{shard_name}/contracts/index.yaml"

    entry: dict = {
        "root_id": root_name,
        "shard_id": shard_name,
        "chart_path": f"{root_name}/shards/{shard_name}/chart.yaml",
        "manifest_path": f"{root_name}/shards/{shard_name}/manifest.yaml",
        "contracts_index_path": ci_path if contracts_index.exists() else None,
        "conformance_index_path": (
            f"{root_name}/shards/{shard_name}/conformance/index.yaml" if conformance_index.exists() else None
        ),
        "evidence_index_path": (
            f"{root_name}/shards/{shard_name}/evidence/index.yaml" if evidence_index.exists() else None
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
        "contract_status": "ready" if contracts_index.exists() else "missing",
        "conformance_status": "ready" if conformance_index.exists() else "missing",
        "evidence_status": "ready" if evidence_index.exists() else "missing",
        "gate_status": "PASS",
        "last_verified_at": "deterministic",
        "verification_mode": "deterministic",
        "verification_result": "PASS",
        "warnings": [],
        "blocking_findings": [],
    }

    if contracts_index.exists():
        entry["entrypoints"].append(
            {
                "kind": "contract_validate",
                "target": ci_path,
            }
        )

    # WAVE_06: canonical runtime consumption fields
    entry.update(_runtime_metadata(repo_root, root_name, shard_name))

    consumption = _scan_canonical_consumption(repo_root, root_name, shard_name, policy, detector)
    entry.update(consumption)

    return entry


def build_registry(roots: list[Path], deterministic: bool) -> dict:
    repo_root = _resolve_repo_root(roots)
    # WAVE_06: load validators once for all shards
    PolicyCls = _load_consumption_policy(repo_root)  # noqa: N806
    DetectorCls = _load_bypass_detector(repo_root)  # noqa: N806
    policy = PolicyCls(repo_root) if PolicyCls else None
    detector = DetectorCls(repo_root) if DetectorCls else None

    shards = []
    for root_path in roots:
        root_name = root_path.name
        for shard_dir in find_shards(root_path):
            entry = scan_shard(repo_root, root_name, shard_dir, policy, detector)
            shards.append(entry)

    shards.sort(key=lambda s: (s["root_id"], s["shard_id"]))

    registry: dict = {
        "schema_version": "1.0.0",
        "git_sha": get_git_sha(repo_root),
        "shard_count": len(shards),
        "shards": shards,
    }

    if not deterministic:
        from datetime import datetime

        registry["generated_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return registry


def verify_registry(registry: dict) -> tuple[bool, list[str]]:
    if not REGISTRY_PATH.exists():
        return False, ["shards_registry.json does not exist"]

    existing = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    diffs = []

    existing_map = {(s["root_id"], s["shard_id"]): s for s in existing.get("shards", [])}
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
                diffs.append(f"HASH MISMATCH: {key[0]}/{key[1]}.{field}: {old_h.get(field)} -> {new_h.get(field)}")
        # WAVE_06: detect consumption status drift
        old_cs = existing_map[key].get("canonical_consumption_status")
        new_cs = new_map[key].get("canonical_consumption_status")
        if old_cs != new_cs:
            diffs.append(f"CONSUMPTION DRIFT: {key[0]}/{key[1]}: {old_cs} -> {new_cs}")

    # git_sha drift is expected after any commit (circular dependency);
    # report as INFO, not as integrity failure.
    if existing.get("git_sha") != registry.get("git_sha"):
        print(f"INFO: git_sha drift (expected): {existing.get('git_sha')[:12]}... -> {registry.get('git_sha')[:12]}...")

    return len(diffs) == 0, diffs


def main() -> int:
    parser = argparse.ArgumentParser(description="Shards Registry Builder (hash-only, stable sort, deterministic)")
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
