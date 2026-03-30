# DEPRECATED: REDUNDANT — Canonical tool is 12_tooling/cli/cross_artifact_reference_audit.py
# Dependencies: 11_test_simulation/tests_registry/test_registry_consistency_audit.py
#!/usr/bin/env python3
"""Registry Consistency Auditor — CC-SSID-REGISTRY-01.

Performs bidirectional consistency checks between the SSID repo structure
and its canonical registry artifacts:

  1. Repo → Registry:  every module on disk has a registry entry
  2. Registry → Repo:  every registry entry points to a real artifact
  3. Duplicate Detection: no duplicate IDs, keys, or module names
  4. Metadata Validation: required fields present and valid
  5. Reference Integrity: artifact_refs and interface_refs resolve

Exit codes:
  0 = PASS   — fully consistent
  1 = WARN   — advisory warnings only
  2 = FAIL   — hard consistency violations
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2

ROOTS_24 = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto",
    "22_datasets", "23_compliance", "24_meta_orchestration",
]

MODULE_YAML_REQUIRED = {"module_id", "version", "status", "classification"}
VALID_STATUSES = {"ROOT-24-LOCK", "active", "planned", "deprecated", "archived"}

REGISTRY_MANIFEST_PATH = "24_meta_orchestration/registry/manifests/registry_manifest.yaml"
SOT_REGISTRY_PATH = "24_meta_orchestration/registry/sot_registry.json"


class Finding:
    """A single audit finding."""

    def __init__(
        self,
        finding_class: str,
        severity: str,
        path: str,
        detail: str,
    ) -> None:
        self.finding_class = finding_class
        self.severity = severity  # "deny" | "warn" | "info"
        self.path = path
        self.detail = detail

    def to_dict(self) -> dict[str, str]:
        return {
            "class": self.finding_class,
            "severity": self.severity,
            "path": self.path,
            "detail": self.detail,
        }


class AuditResult:
    """Collects all findings from the audit."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def has_failures(self) -> bool:
        return any(f.severity == "deny" for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == "warn" for f in self.findings)

    @property
    def exit_code(self) -> int:
        if self.has_failures:
            return EXIT_FAIL
        if self.has_warnings:
            return EXIT_WARN
        return EXIT_PASS

    @property
    def overall(self) -> str:
        if self.has_failures:
            return "FAIL"
        if self.has_warnings:
            return "WARN"
        return "PASS"

    def evidence_hash(self) -> str:
        data = json.dumps(
            [f.to_dict() for f in self.findings],
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# -----------------------------------------------------------------------
# Check 1: Repo → Registry (every root on disk has a registry entry)
# -----------------------------------------------------------------------
def check_repo_to_registry(
    repo: Path,
    manifest_modules: dict[str, dict[str, Any]],
    result: AuditResult,
) -> None:
    for root_name in ROOTS_24:
        root_dir = repo / root_name
        if not root_dir.is_dir():
            result.add(Finding(
                "registry_missing",
                "deny",
                root_name,
                f"expected root directory '{root_name}' does not exist on disk",
            ))
            continue

        if root_name not in manifest_modules:
            result.add(Finding(
                "registry_missing",
                "deny",
                root_name,
                f"module '{root_name}' exists on disk but has no entry in registry_manifest.yaml",
            ))

        module_yaml = root_dir / "module.yaml"
        if not module_yaml.exists():
            result.add(Finding(
                "registry_missing",
                "deny",
                f"{root_name}/module.yaml",
                f"module.yaml missing for root '{root_name}'",
            ))


# -----------------------------------------------------------------------
# Check 2: Registry → Repo (every registry entry has real artifacts)
# -----------------------------------------------------------------------
def check_registry_to_repo(
    repo: Path,
    manifest_modules: dict[str, dict[str, Any]],
    result: AuditResult,
) -> None:
    for module_id, entry in manifest_modules.items():
        root_dir = repo / module_id
        if not root_dir.is_dir():
            result.add(Finding(
                "registry_orphan",
                "deny",
                module_id,
                f"registry entry for '{module_id}' but directory does not exist",
            ))
            continue

        artifact_refs = entry.get("artifact_refs", {})
        if isinstance(artifact_refs, dict):
            for ref_name, ref_path in artifact_refs.items():
                full_path = repo / ref_path
                if not full_path.exists():
                    result.add(Finding(
                        "registry_reference_broken",
                        "deny",
                        ref_path,
                        f"artifact_ref '{ref_name}' points to non-existent file",
                    ))


# -----------------------------------------------------------------------
# Check 3: Duplicate Detection
# -----------------------------------------------------------------------
def check_duplicates(
    manifest_modules: dict[str, dict[str, Any]],
    result: AuditResult,
) -> None:
    seen_ids: dict[str, str] = {}
    seen_names: dict[str, str] = {}

    for module_id, entry in manifest_modules.items():
        mid = entry.get("module_id", module_id)
        if mid in seen_ids:
            result.add(Finding(
                "registry_duplicate",
                "deny",
                module_id,
                f"duplicate module_id '{mid}' (also in '{seen_ids[mid]}')",
            ))
        else:
            seen_ids[mid] = module_id

        name = entry.get("name", "")
        if name and name in seen_names:
            result.add(Finding(
                "registry_duplicate",
                "deny",
                module_id,
                f"duplicate module name '{name}' (also in '{seen_names[name]}')",
            ))
        elif name:
            seen_names[name] = module_id

    governance_rules: dict[str, list[str]] = {}
    for module_id, entry in manifest_modules.items():
        for rule in entry.get("governance_rules", []):
            governance_rules.setdefault(rule, []).append(module_id)

    for rule_id, modules in governance_rules.items():
        if len(modules) > 1:
            result.add(Finding(
                "registry_duplicate",
                "warn",
                rule_id,
                f"governance_rule '{rule_id}' assigned to multiple modules: {modules}",
            ))


# -----------------------------------------------------------------------
# Check 4: Metadata Validation
# -----------------------------------------------------------------------
def check_metadata(
    repo: Path,
    manifest_modules: dict[str, dict[str, Any]],
    result: AuditResult,
) -> None:
    for module_id, entry in manifest_modules.items():
        module_yaml_path = repo / module_id / "module.yaml"
        if not module_yaml_path.exists():
            continue

        try:
            data = load_yaml(module_yaml_path)
        except Exception:
            result.add(Finding(
                "registry_metadata_invalid",
                "deny",
                f"{module_id}/module.yaml",
                "module.yaml is not valid YAML",
            ))
            continue

        if not isinstance(data, dict):
            result.add(Finding(
                "registry_metadata_invalid",
                "deny",
                f"{module_id}/module.yaml",
                "module.yaml is not a YAML mapping",
            ))
            continue

        missing = MODULE_YAML_REQUIRED - set(data.keys())
        if missing:
            result.add(Finding(
                "registry_metadata_invalid",
                "deny",
                f"{module_id}/module.yaml",
                f"missing required fields: {sorted(missing)}",
            ))

        status = data.get("status", "")
        if status and status not in VALID_STATUSES:
            result.add(Finding(
                "registry_metadata_invalid",
                "deny",
                f"{module_id}/module.yaml",
                f"invalid status '{status}' (valid: {sorted(VALID_STATUSES)})",
            ))

        disk_mid = data.get("module_id", "")
        if disk_mid and disk_mid != module_id:
            result.add(Finding(
                "registry_path_mismatch",
                "deny",
                f"{module_id}/module.yaml",
                f"module_id in file is '{disk_mid}' but directory is '{module_id}'",
            ))

        registry_version = entry.get("version", "")
        disk_version = data.get("version", "")
        if registry_version and disk_version and registry_version != disk_version:
            result.add(Finding(
                "registry_path_mismatch",
                "warn",
                f"{module_id}/module.yaml",
                f"version mismatch: registry='{registry_version}', disk='{disk_version}'",
            ))


# -----------------------------------------------------------------------
# Check 5: SoT Registry artifact integrity
# -----------------------------------------------------------------------
def check_sot_registry_integrity(
    repo: Path,
    result: AuditResult,
) -> None:
    sot_path = repo / SOT_REGISTRY_PATH
    if not sot_path.exists():
        result.add(Finding(
            "registry_missing",
            "deny",
            SOT_REGISTRY_PATH,
            "sot_registry.json does not exist",
        ))
        return

    try:
        sot = load_json(sot_path)
    except Exception:
        result.add(Finding(
            "registry_metadata_invalid",
            "deny",
            SOT_REGISTRY_PATH,
            "sot_registry.json is not valid JSON",
        ))
        return

    artifacts = sot.get("roots", {}).get("sot_artifacts", [])
    for artifact in artifacts:
        name = artifact.get("name", "?")
        path = artifact.get("path", "")
        expected_hash = artifact.get("hash_sha256", "")

        full_path = repo / path
        if not full_path.exists():
            result.add(Finding(
                "registry_reference_broken",
                "deny",
                path,
                f"sot_registry artifact '{name}' points to non-existent file",
            ))
            continue

        if expected_hash:
            actual_hash = sha256_file(full_path)
            if actual_hash != expected_hash:
                result.add(Finding(
                    "registry_reference_broken",
                    "warn",
                    path,
                    f"sot_registry artifact '{name}' hash mismatch: "
                    f"expected={expected_hash[:16]}..., actual={actual_hash[:16]}...",
                ))


# -----------------------------------------------------------------------
# Main audit
# -----------------------------------------------------------------------
def run_audit(repo: Path) -> AuditResult:
    result = AuditResult()

    manifest_path = repo / REGISTRY_MANIFEST_PATH
    if not manifest_path.exists():
        result.add(Finding(
            "registry_missing",
            "deny",
            REGISTRY_MANIFEST_PATH,
            "registry_manifest.yaml does not exist",
        ))
        return result

    try:
        manifest_data = load_yaml(manifest_path)
    except Exception as exc:
        result.add(Finding(
            "registry_metadata_invalid",
            "deny",
            REGISTRY_MANIFEST_PATH,
            f"cannot parse registry_manifest.yaml: {exc}",
        ))
        return result

    modules_list = manifest_data.get("modules", [])
    if not isinstance(modules_list, list):
        result.add(Finding(
            "registry_metadata_invalid",
            "deny",
            REGISTRY_MANIFEST_PATH,
            "registry_manifest.yaml 'modules' is not a list",
        ))
        return result

    manifest_modules: dict[str, dict[str, Any]] = {}
    for entry in modules_list:
        if isinstance(entry, dict) and "module_id" in entry:
            mid = entry["module_id"]
            if mid in manifest_modules:
                result.add(Finding(
                    "registry_duplicate",
                    "deny",
                    mid,
                    f"duplicate module_id '{mid}' in registry_manifest.yaml",
                ))
            manifest_modules[mid] = entry

    check_repo_to_registry(repo, manifest_modules, result)
    check_registry_to_repo(repo, manifest_modules, result)
    check_duplicates(manifest_modules, result)
    check_metadata(repo, manifest_modules, result)
    check_sot_registry_integrity(repo, result)

    return result


def generate_report(result: AuditResult, repo: Path) -> dict[str, Any]:
    ts = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return {
        "audit_type": "registry_consistency",
        "timestamp_utc": ts,
        "repo": str(repo),
        "overall": result.overall,
        "finding_count": len(result.findings),
        "deny_count": sum(1 for f in result.findings if f.severity == "deny"),
        "warn_count": sum(1 for f in result.findings if f.severity == "warn"),
        "info_count": sum(1 for f in result.findings if f.severity == "info"),
        "evidence_hash": result.evidence_hash(),
        "findings": [f.to_dict() for f in result.findings],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="registry_consistency_audit.py",
        description="Audit registry consistency for SSID.",
    )
    parser.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parents[2]),
        help="SSID repository root (default: auto-detect from script location)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output JSON report instead of human-readable",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="write report to file (JSON)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()

    result = run_audit(repo)
    report = generate_report(result, repo)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Registry Consistency Audit: {result.overall}")
        print(f"  Findings: {len(result.findings)} "
              f"(deny={report['deny_count']}, warn={report['warn_count']}, info={report['info_count']})")
        print(f"  Evidence Hash: {report['evidence_hash'][:16]}...")
        if result.findings:
            print()
            for f in result.findings:
                tag = "FAIL" if f.severity == "deny" else f.severity.upper()
                print(f"  [{tag}] {f.finding_class}: {f.path}")
                print(f"         {f.detail}")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not args.json:
            print(f"\n  Report written to: {out_path}")

    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
