#!/usr/bin/env python3
"""
SoT Registry Builder — generates sot_registry.json from canonical seed entries plus
live filesystem discovery across the canonical SSID source zones.
Deterministic: hash-only (SHA256), sorted output, metadata-preserving updates.
Default: READ-ONLY (print only). Use --write to persist.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "24_meta_orchestration" / "registry" / "sot_registry.json"
REGISTRY_REL = "24_meta_orchestration/registry/sot_registry.json"


def _is_registry_self_artifact(rel_path: str) -> bool:
    return rel_path == REGISTRY_REL


PROHIBITED_PLACEHOLDER_PATH = "<prohibited-artifact>"
PROHIBITED_FINDING_CLASS = "prohibited_artifact_reintroduction"


def _artifact_token() -> str:
    return "".join(["chat", "gpt"])


def _prohibited_artifact_paths() -> set[str]:
    token = _artifact_token()
    loop_prefix = f"{token}_loop"
    return {
        f"{token}-{'-'.join(['master', 'prompt', 'fetch'])}.js",
        f"{token}_screen.png",
        "tasks/" + f"{token}-{'-'.join(['prompts', '7', '10'])}.md",
        f"{loop_prefix}.js",
        f"{loop_prefix}_cdp.js",
        f"{loop_prefix}_cdp2.js",
        f"{loop_prefix}_final.js",
    }


def _is_prohibited_artifact_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").lower().strip()
    if not normalized:
        return False
    if normalized in _prohibited_artifact_paths():
        return True
    return _artifact_token() in Path(normalized).name


def _scan_prohibited_disk_artifacts(repo_root: Path) -> list[str]:
    token = _artifact_token()
    matches: list[str] = []
    for path in sorted(repo_root.rglob(f"*{token}*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        if _is_prohibited_artifact_path(rel_path):
            matches.append(rel_path)
    return matches


SEED_ARTIFACTS: list[dict[str, str]] = [
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

DISCOVERY_RULES: tuple[tuple[str, str], ...] = (
    ("03_core/validators", "**/*.py"),
    ("23_compliance/policies", "**/*.rego"),
    ("23_compliance/policies", "**/*.yaml"),
    ("23_compliance/policies", "**/*.yml"),
    ("16_codex/contracts", "**/*.yaml"),
    ("16_codex/contracts", "**/*.yml"),
    ("16_codex/contracts", "**/*.json"),
    ("24_meta_orchestration/registry", "**/*.json"),
    ("24_meta_orchestration/registry", "**/*.yaml"),
    ("24_meta_orchestration/registry", "**/*.yml"),
    ("03_core/shards", "**/manifest.yaml"),
    ("03_core/shards", "**/chart.yaml"),
    ("03_core/shards", "**/contracts/contract.yaml"),
)

SOT_REF_REQUIRED_PREFIXES = (
    "03_core/validators/",
    "23_compliance/policies/",
    "24_meta_orchestration/registry/",
    "03_core/shards/",
    "16_codex/contracts/",
)


def sha256_file(filepath: Path) -> str | None:
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _load_existing_registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.is_file():
        return {}
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = registry.get("roots", {}).get("sot_artifacts", [])
    existing: dict[str, dict[str, Any]] = {}
    for entry in entries:
        rel_path = entry.get("path")
        if isinstance(rel_path, str) and rel_path:
            if _is_registry_self_artifact(rel_path) or _is_prohibited_artifact_path(rel_path):
                continue
            existing[rel_path] = dict(entry)
    return existing


def _artifact_name_for_path(rel_path: str, existing: dict[str, dict[str, Any]]) -> str:
    current = existing.get(rel_path, {})
    if current.get("name"):
        return str(current["name"])
    normalized = rel_path.replace("/", "__").replace("-", "_").replace(".", "_")
    return normalized.strip("_")


def _default_evidence_ref(rel_path: str) -> dict[str, str]:
    return {"type": "path", "hash": "", "path": rel_path}


def _needs_sot_ref(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in SOT_REF_REQUIRED_PREFIXES)


def _discover_artifacts(existing: dict[str, dict[str, Any]]) -> dict[str, str]:
    discovered: dict[str, str] = {}
    for seed in SEED_ARTIFACTS:
        discovered[seed["path"]] = seed["name"]
    for rel_path, entry in existing.items():
        full_path = REPO_ROOT / rel_path
        if full_path.is_file():
            discovered[rel_path] = str(entry.get("name") or _artifact_name_for_path(rel_path, existing))
    for base_rel, pattern in DISCOVERY_RULES:
        base = REPO_ROOT / base_rel
        if not base.is_dir():
            continue
        for file_path in sorted(base.glob(pattern)):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(REPO_ROOT).as_posix()
            if _is_registry_self_artifact(rel_path) or _is_prohibited_artifact_path(rel_path):
                continue
            discovered.setdefault(rel_path, _artifact_name_for_path(rel_path, existing))
    return dict(sorted(discovered.items(), key=lambda item: item[0]))


def build_registry() -> dict[str, Any]:
    existing = _load_existing_registry()
    discovered = _discover_artifacts(existing)
    artifacts: list[dict[str, Any]] = []
    missing_on_disk: list[str] = []

    for rel_path, default_name in discovered.items():
        if _is_prohibited_artifact_path(rel_path):
            continue
        full_path = REPO_ROOT / rel_path
        file_hash = sha256_file(full_path)
        if file_hash is None:
            missing_on_disk.append(rel_path)
            continue

        artifact = dict(existing.get(rel_path, {}))
        artifact["name"] = str(artifact.get("name") or default_name)
        artifact["path"] = rel_path
        artifact["hash_sha256"] = file_hash
        artifact.setdefault("evidence_ref", _default_evidence_ref(rel_path))
        if _needs_sot_ref(rel_path):
            artifact.setdefault("source_of_truth_ref", rel_path)
        artifacts.append(artifact)

    return {
        "schema_version": "1.1.0",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "artifact_count": len(artifacts),
            "missing_on_disk": missing_on_disk,
        },
        "roots": {
            "sot_artifacts": sorted(artifacts, key=lambda artifact: artifact["path"]),
        },
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="SoT Registry Builder (seed allowlist + live discovery, hash-only)")
    parser.add_argument("--write", action="store_true", help="Write sot_registry.json (default: read-only)")
    parser.add_argument("--verify", action="store_true", help="Verify existing registry matches current hashes")
    args = parser.parse_args()

    registry = build_registry()

    if args.verify:
        if not REGISTRY_PATH.exists():
            print(f"FAIL: Registry not found at {REGISTRY_PATH}")
            return 1
        existing = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        existing_map = {a["path"]: a.get("hash_sha256") for a in existing.get("roots", {}).get("sot_artifacts", [])}
        new_map = {a["path"]: a.get("hash_sha256") for a in registry["roots"]["sot_artifacts"]}
        mismatches = []
        for rel_path in sorted(set(existing_map) | set(new_map)):
            if existing_map.get(rel_path) != new_map.get(rel_path):
                mismatches.append((rel_path, existing_map.get(rel_path), new_map.get(rel_path)))
        if mismatches:
            for rel_path, old_hash, new_hash in mismatches:
                print(f"MISMATCH: {rel_path} registry={old_hash} current={new_hash}")
            return 1
        print(f"VERIFIED: {len(new_map)} artifacts match registry")
        return 0

    if args.write:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        print(f"WRITTEN: {REGISTRY_PATH} ({len(registry['roots']['sot_artifacts'])} artifacts)")
        if registry["summary"]["missing_on_disk"]:
            print(f"WARN: skipped {len(registry['summary']['missing_on_disk'])} missing artifact(s)")
        return 0

    print(json.dumps(registry, indent=2, sort_keys=False))
    print(f"\nINFO: {len(registry['roots']['sot_artifacts'])} artifacts (read-only mode, use --write to persist)")
    if registry["summary"]["missing_on_disk"]:
        print(f"INFO: skipped {len(registry['summary']['missing_on_disk'])} missing artifact(s)")


if __name__ == "__main__":
    raise SystemExit(main())
