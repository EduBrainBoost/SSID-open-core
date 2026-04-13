#!/usr/bin/env python3
"""Convergence Checker — Contract/Schema/Registry Convergence Audit.

Verifies cross-artifact consistency for ALL 24 SSID roots:

  Check 1: manifest.yaml status/version must match module.yaml (SoT)
  Check 2: manifest.yaml classification must match module.yaml
  Check 3: manifest.yaml contract refs must point to existing paths
  Check 4: manifest.yaml shard declarations must match actual shard dirs
  Check 5: chart.yaml capabilities must align with manifest implementation_stack
  Check 6: module.yaml status must match registry_manifest.yaml status
  Check 7: registry tasks must reference correct root paths
  Check 8: module.yaml YAML well-formedness (BOM, multi-doc, encoding)
  Check 9: manifest.yaml governance_rules vs module.yaml governance_rules

Output: JSON report with PASS/FAIL per root + findings.

Exit codes:
  0 = PASS   — fully consistent
  1 = WARN   — advisory warnings only
  2 = FAIL   — hard consistency violations
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2

ROOTS_24 = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]

REGISTRY_MANIFEST_PATH = "24_meta_orchestration/registry/manifests/registry_manifest.yaml"
TASKS_DIR = "24_meta_orchestration/registry/tasks"

STANDARD_SHARDS = [
    "01_identitaet_personen",
    "02_dokumente_nachweise",
    "03_zugang_berechtigungen",
    "04_kommunikation_daten",
    "05_gesundheit_medizin",
    "06_bildung_qualifikationen",
    "07_familie_soziales",
    "08_mobilitaet_fahrzeuge",
    "09_arbeit_karriere",
    "10_finanzen_banking",
    "11_versicherungen_risiken",
    "12_immobilien_grundstuecke",
    "13_unternehmen_gewerbe",
    "14_vertraege_vereinbarungen",
    "15_handel_transaktionen",
    "16_behoerden_verwaltung",
]


class Finding:
    """A single convergence finding."""

    def __init__(
        self,
        check_id: str,
        severity: str,
        root: str,
        path: str,
        detail: str,
    ) -> None:
        self.check_id = check_id
        self.severity = severity  # "deny" | "warn" | "info"
        self.root = root
        self.path = path
        self.detail = detail

    def to_dict(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "root": self.root,
            "path": self.path,
            "detail": self.detail,
        }


class ConvergenceResult:
    """Collects all findings from the convergence check."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.root_results: dict[str, str] = {}

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def compute_root_results(self) -> None:
        """Compute per-root PASS/FAIL/WARN status."""
        for root in ROOTS_24:
            root_findings = [f for f in self.findings if f.root == root]
            if any(f.severity == "deny" for f in root_findings):
                self.root_results[root] = "FAIL"
            elif any(f.severity == "warn" for f in root_findings):
                self.root_results[root] = "WARN"
            else:
                self.root_results[root] = "PASS"

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


def _load_yaml_safe(path: Path) -> tuple[Any, str | None]:
    """Load YAML, handling BOM and returning (data, error_msg)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = yaml.safe_load(text)
        return data, None
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"
    except Exception as exc:
        return None, f"read error: {exc}"


def _load_json_safe(path: Path) -> tuple[Any, str | None]:
    """Load JSON, returning (data, error_msg)."""
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return data, None
    except Exception as exc:
        return None, f"JSON parse error: {exc}"


# -----------------------------------------------------------------------
# Check 1: manifest.yaml status/version must match module.yaml
# -----------------------------------------------------------------------
def check_status_version_convergence(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        mod_path = repo / root / "module.yaml"
        man_path = repo / root / "manifest.yaml"

        if not mod_path.exists() or not man_path.exists():
            continue

        mod_data, mod_err = _load_yaml_safe(mod_path)
        man_data, man_err = _load_yaml_safe(man_path)

        if mod_err or man_err:
            continue  # handled by check_yaml_wellformedness

        if not isinstance(mod_data, dict) or not isinstance(man_data, dict):
            continue

        mod_status = mod_data.get("status", "")
        man_status = man_data.get("status", "")
        if mod_status and man_status and mod_status != man_status:
            result.add(
                Finding(
                    "CVG-001",
                    "deny",
                    root,
                    f"{root}/manifest.yaml",
                    f"status mismatch: module.yaml='{mod_status}', manifest.yaml='{man_status}'",
                )
            )

        mod_ver = str(mod_data.get("version", ""))
        man_ver = str(man_data.get("version", ""))
        if mod_ver and man_ver and mod_ver != man_ver:
            result.add(
                Finding(
                    "CVG-001",
                    "deny",
                    root,
                    f"{root}/manifest.yaml",
                    f"version mismatch: module.yaml='{mod_ver}', manifest.yaml='{man_ver}'",
                )
            )


# -----------------------------------------------------------------------
# Check 2: manifest.yaml classification must match module.yaml
# -----------------------------------------------------------------------
def check_classification_convergence(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        mod_path = repo / root / "module.yaml"
        man_path = repo / root / "manifest.yaml"

        if not mod_path.exists() or not man_path.exists():
            continue

        mod_data, _ = _load_yaml_safe(mod_path)
        man_data, _ = _load_yaml_safe(man_path)

        if not isinstance(mod_data, dict) or not isinstance(man_data, dict):
            continue

        mod_cls = mod_data.get("classification", "")
        man_cls = man_data.get("classification", "")
        if mod_cls and man_cls and mod_cls != man_cls:
            result.add(
                Finding(
                    "CVG-002",
                    "warn",
                    root,
                    f"{root}/manifest.yaml",
                    f"classification mismatch: module.yaml='{mod_cls}', manifest.yaml='{man_cls}'",
                )
            )


# -----------------------------------------------------------------------
# Check 3: manifest.yaml contract refs must point to existing paths
# -----------------------------------------------------------------------
def check_contract_refs(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        man_path = repo / root / "manifest.yaml"
        if not man_path.exists():
            continue

        man_data, _ = _load_yaml_safe(man_path)
        if not isinstance(man_data, dict):
            continue

        contracts = man_data.get("contracts", [])
        if not isinstance(contracts, list):
            continue

        for entry in contracts:
            if isinstance(entry, dict):
                ref = entry.get("ref", "")
            elif isinstance(entry, str):
                ref = entry
            else:
                continue

            if not ref:
                continue

            full_path = repo / root / ref
            if not full_path.exists():
                result.add(
                    Finding(
                        "CVG-003",
                        "deny",
                        root,
                        f"{root}/{ref}",
                        f"contract ref '{ref}' in manifest.yaml does not exist on disk",
                    )
                )


# -----------------------------------------------------------------------
# Check 4: manifest.yaml shard declarations vs actual shard dirs
# -----------------------------------------------------------------------
def check_shard_declarations(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        man_path = repo / root / "manifest.yaml"
        if not man_path.exists():
            continue

        man_data, _ = _load_yaml_safe(man_path)
        if not isinstance(man_data, dict):
            continue

        shards_block = man_data.get("shards", {})
        if not isinstance(shards_block, dict):
            continue

        declared_count = shards_block.get("count", 0)
        declared_list = shards_block.get("shards_list", [])

        shards_dir = repo / root / "shards"
        if not shards_dir.is_dir():
            if declared_count > 0 or declared_list:
                result.add(
                    Finding(
                        "CVG-004",
                        "warn",
                        root,
                        f"{root}/shards/",
                        f"manifest declares {declared_count} shards but shards/ directory does not exist",
                    )
                )
            continue

        actual_shards = sorted([d.name for d in shards_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])

        if isinstance(declared_list, list) and declared_list:
            declared_set = set(declared_list)
            actual_set = set(actual_shards)

            missing_on_disk = declared_set - actual_set
            for s in sorted(missing_on_disk):
                result.add(
                    Finding(
                        "CVG-004",
                        "deny",
                        root,
                        f"{root}/shards/{s}",
                        f"shard '{s}' declared in manifest but missing on disk",
                    )
                )

            extra_on_disk = actual_set - declared_set
            for s in sorted(extra_on_disk):
                result.add(
                    Finding(
                        "CVG-004",
                        "warn",
                        root,
                        f"{root}/shards/{s}",
                        f"shard '{s}' exists on disk but not declared in manifest",
                    )
                )

        if declared_count and len(actual_shards) != declared_count:
            result.add(
                Finding(
                    "CVG-004",
                    "warn",
                    root,
                    f"{root}/shards/",
                    f"manifest declares count={declared_count} but {len(actual_shards)} shard dirs found on disk",
                )
            )


# -----------------------------------------------------------------------
# Check 5: chart.yaml capabilities vs manifest implementation_stack
# -----------------------------------------------------------------------
def check_chart_manifest_alignment(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        shards_dir = repo / root / "shards"
        if not shards_dir.is_dir():
            continue

        for shard_dir in sorted(shards_dir.iterdir()):
            if not shard_dir.is_dir() or shard_dir.name.startswith("."):
                continue

            chart_path = shard_dir / "chart.yaml"
            manifest_path = shard_dir / "manifest.yaml"

            chart_exists = chart_path.exists()
            manifest_exists = manifest_path.exists()

            if not chart_exists and not manifest_exists:
                result.add(
                    Finding(
                        "CVG-005",
                        "warn",
                        root,
                        f"{root}/shards/{shard_dir.name}/",
                        "shard has neither chart.yaml nor manifest.yaml",
                    )
                )
                continue

            if chart_exists and not manifest_exists:
                result.add(
                    Finding(
                        "CVG-005",
                        "warn",
                        root,
                        f"{root}/shards/{shard_dir.name}/manifest.yaml",
                        "shard has chart.yaml but no manifest.yaml",
                    )
                )
                continue

            if not chart_exists and manifest_exists:
                result.add(
                    Finding(
                        "CVG-005",
                        "warn",
                        root,
                        f"{root}/shards/{shard_dir.name}/chart.yaml",
                        "shard has manifest.yaml but no chart.yaml",
                    )
                )
                continue

            # Both exist: check alignment
            chart_data, chart_err = _load_yaml_safe(chart_path)
            manifest_data, manifest_err = _load_yaml_safe(manifest_path)

            if chart_err or manifest_err:
                continue

            if not isinstance(chart_data, dict) or not isinstance(manifest_data, dict):
                continue

            # Check root_id consistency
            chart_root = chart_data.get("root", "")
            manifest_root = manifest_data.get("root_id", "")
            if chart_root and manifest_root and chart_root != manifest_root:
                result.add(
                    Finding(
                        "CVG-005",
                        "deny",
                        root,
                        f"{root}/shards/{shard_dir.name}/",
                        f"root mismatch: chart.root='{chart_root}', manifest.root_id='{manifest_root}'",
                    )
                )

            # Check shard_id consistency
            chart_shard = chart_data.get("shard", "")
            manifest_shard = manifest_data.get("shard_id", "")
            if chart_shard and manifest_shard and chart_shard != manifest_shard:
                result.add(
                    Finding(
                        "CVG-005",
                        "deny",
                        root,
                        f"{root}/shards/{shard_dir.name}/",
                        f"shard id mismatch: chart.shard='{chart_shard}', manifest.shard_id='{manifest_shard}'",
                    )
                )

            # Check status consistency
            chart_status = chart_data.get("status", "")
            manifest_stack = manifest_data.get("implementation_stack", "")
            if chart_status and isinstance(manifest_stack, str) and manifest_stack:
                # implementation_stack as string (e.g., "generated") is a
                # placeholder; if chart has real capabilities but manifest
                # just says "generated", that is a convergence gap
                chart_caps = chart_data.get("capabilities", {})
                if isinstance(chart_caps, dict):
                    must_caps = chart_caps.get("must", [])
                    if must_caps and manifest_stack == "generated":
                        result.add(
                            Finding(
                                "CVG-005",
                                "info",
                                root,
                                f"{root}/shards/{shard_dir.name}/",
                                f"chart defines {len(must_caps)} MUST capabilities "
                                f"but manifest implementation_stack='generated'",
                            )
                        )


# -----------------------------------------------------------------------
# Check 6: module.yaml status must match registry_manifest.yaml
# -----------------------------------------------------------------------
def check_registry_convergence(
    repo: Path,
    registry_modules: dict[str, dict[str, Any]],
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        mod_path = repo / root / "module.yaml"
        if not mod_path.exists():
            continue

        mod_data, mod_err = _load_yaml_safe(mod_path)
        if mod_err or not isinstance(mod_data, dict):
            continue

        if root not in registry_modules:
            result.add(
                Finding(
                    "CVG-006",
                    "deny",
                    root,
                    REGISTRY_MANIFEST_PATH,
                    f"root '{root}' has module.yaml but no entry in registry_manifest.yaml",
                )
            )
            continue

        reg_entry = registry_modules[root]

        # Status
        mod_status = mod_data.get("status", "")
        reg_status = reg_entry.get("status", "")
        if mod_status and reg_status and mod_status != reg_status:
            result.add(
                Finding(
                    "CVG-006",
                    "deny",
                    root,
                    f"{root}/module.yaml",
                    f"status mismatch: module.yaml='{mod_status}', registry='{reg_status}'",
                )
            )

        # Version
        mod_ver = str(mod_data.get("version", ""))
        reg_ver = str(reg_entry.get("version", ""))
        if mod_ver and reg_ver and mod_ver != reg_ver:
            result.add(
                Finding(
                    "CVG-006",
                    "warn",
                    root,
                    f"{root}/module.yaml",
                    f"version mismatch: module.yaml='{mod_ver}', registry='{reg_ver}'",
                )
            )

        # Name
        mod_name = mod_data.get("name", "")
        reg_name = reg_entry.get("name", "")
        if mod_name and reg_name and mod_name != reg_name:
            result.add(
                Finding(
                    "CVG-006",
                    "warn",
                    root,
                    f"{root}/module.yaml",
                    f"name mismatch: module.yaml='{mod_name}', registry='{reg_name}'",
                )
            )


# -----------------------------------------------------------------------
# Check 7: registry tasks reference correct root paths
# -----------------------------------------------------------------------
def check_task_root_paths(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    tasks_dir = repo / TASKS_DIR
    if not tasks_dir.is_dir():
        result.add(
            Finding(
                "CVG-007",
                "warn",
                "24_meta_orchestration",
                TASKS_DIR,
                "registry tasks directory does not exist",
            )
        )
        return

    for task_file in sorted(tasks_dir.glob("TASK_CHART_MANIFEST_BACKFILL_*.json")):
        data, err = _load_json_safe(task_file)
        if err or not isinstance(data, dict):
            result.add(
                Finding(
                    "CVG-007",
                    "warn",
                    "24_meta_orchestration",
                    str(task_file.relative_to(repo)),
                    f"cannot parse task file: {err}",
                )
            )
            continue

        scopes = data.get("scope_paths_allow", [])
        if not scopes:
            continue

        # Extract root from first scope path
        first_scope = scopes[0] if scopes else ""
        root_name = first_scope.split("/")[0] if "/" in first_scope else ""

        if root_name and root_name not in ROOTS_24:
            result.add(
                Finding(
                    "CVG-007",
                    "deny",
                    "24_meta_orchestration",
                    str(task_file.relative_to(repo)),
                    f"task references unknown root '{root_name}'",
                )
            )

        if root_name and not (repo / root_name).is_dir():
            result.add(
                Finding(
                    "CVG-007",
                    "deny",
                    "24_meta_orchestration",
                    str(task_file.relative_to(repo)),
                    f"task scope references non-existent directory '{root_name}'",
                )
            )


# -----------------------------------------------------------------------
# Check 8: YAML well-formedness (BOM, encoding)
# -----------------------------------------------------------------------
def check_yaml_wellformedness(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        for fname in ("module.yaml", "manifest.yaml"):
            fpath = repo / root / fname
            if not fpath.exists():
                if fname == "module.yaml":
                    result.add(
                        Finding(
                            "CVG-008",
                            "deny",
                            root,
                            f"{root}/{fname}",
                            f"{fname} does not exist",
                        )
                    )
                elif fname == "manifest.yaml":
                    result.add(
                        Finding(
                            "CVG-008",
                            "warn",
                            root,
                            f"{root}/{fname}",
                            f"{fname} does not exist",
                        )
                    )
                continue

            raw = fpath.read_bytes()

            # BOM check
            if raw.startswith(b"\xef\xbb\xbf"):
                result.add(
                    Finding(
                        "CVG-008",
                        "warn",
                        root,
                        f"{root}/{fname}",
                        f"{fname} contains UTF-8 BOM (should be plain UTF-8)",
                    )
                )

            # Parse check (using utf-8-sig to handle BOM gracefully)
            _, parse_err = _load_yaml_safe(fpath)
            if parse_err:
                result.add(
                    Finding(
                        "CVG-008",
                        "deny",
                        root,
                        f"{root}/{fname}",
                        f"{fname} {parse_err}",
                    )
                )


# -----------------------------------------------------------------------
# Check 9: governance_rules consistency (manifest vs module)
# -----------------------------------------------------------------------
def check_governance_rules_convergence(
    repo: Path,
    result: ConvergenceResult,
) -> None:
    for root in ROOTS_24:
        mod_path = repo / root / "module.yaml"
        man_path = repo / root / "manifest.yaml"

        if not mod_path.exists() or not man_path.exists():
            continue

        mod_data, _ = _load_yaml_safe(mod_path)
        man_data, _ = _load_yaml_safe(man_path)

        if not isinstance(mod_data, dict) or not isinstance(man_data, dict):
            continue

        mod_rules = mod_data.get("governance_rules", [])
        man_rules = man_data.get("governance_rules", [])

        if not isinstance(mod_rules, list):
            mod_rules = []
        if not isinstance(man_rules, list):
            man_rules = []

        mod_set = set(mod_rules)
        man_set = set(man_rules)

        if mod_set and man_set and mod_set != man_set:
            result.add(
                Finding(
                    "CVG-009",
                    "warn",
                    root,
                    f"{root}/",
                    f"governance_rules mismatch: module.yaml={sorted(mod_set)}, manifest.yaml={sorted(man_set)}",
                )
            )
        elif mod_set and not man_set:
            result.add(
                Finding(
                    "CVG-009",
                    "info",
                    root,
                    f"{root}/manifest.yaml",
                    f"module.yaml has governance_rules {sorted(mod_set)} but manifest.yaml has empty governance_rules",
                )
            )


# -----------------------------------------------------------------------
# Main convergence check
# -----------------------------------------------------------------------
def run_convergence(repo: Path) -> ConvergenceResult:
    result = ConvergenceResult()

    # Load registry manifest for Check 6
    registry_modules: dict[str, dict[str, Any]] = {}
    reg_path = repo / REGISTRY_MANIFEST_PATH
    if reg_path.exists():
        reg_data, reg_err = _load_yaml_safe(reg_path)
        if reg_err:
            result.add(
                Finding(
                    "CVG-006",
                    "deny",
                    "24_meta_orchestration",
                    REGISTRY_MANIFEST_PATH,
                    f"cannot parse registry_manifest.yaml: {reg_err}",
                )
            )
        elif isinstance(reg_data, dict):
            modules_list = reg_data.get("modules", [])
            if isinstance(modules_list, list):
                for entry in modules_list:
                    if isinstance(entry, dict) and "module_id" in entry:
                        registry_modules[entry["module_id"]] = entry

    # Run all checks
    check_yaml_wellformedness(repo, result)
    check_status_version_convergence(repo, result)
    check_classification_convergence(repo, result)
    check_contract_refs(repo, result)
    check_shard_declarations(repo, result)
    check_chart_manifest_alignment(repo, result)
    check_registry_convergence(repo, registry_modules, result)
    check_task_root_paths(repo, result)
    check_governance_rules_convergence(repo, result)

    result.compute_root_results()
    return result


def generate_report(result: ConvergenceResult, repo: Path) -> dict[str, Any]:
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "audit_type": "convergence_check",
        "timestamp_utc": ts,
        "repo": str(repo),
        "overall": result.overall,
        "finding_count": len(result.findings),
        "deny_count": sum(1 for f in result.findings if f.severity == "deny"),
        "warn_count": sum(1 for f in result.findings if f.severity == "warn"),
        "info_count": sum(1 for f in result.findings if f.severity == "info"),
        "evidence_hash": result.evidence_hash(),
        "root_results": result.root_results,
        "findings": [f.to_dict() for f in result.findings],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="convergence_checker.py",
        description="Contract/Schema/Registry Convergence Audit for SSID.",
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

    result = run_convergence(repo)
    report = generate_report(result, repo)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Convergence Check: {result.overall}")
        print(
            f"  Findings: {len(result.findings)} "
            f"(deny={report['deny_count']}, "
            f"warn={report['warn_count']}, "
            f"info={report['info_count']})"
        )
        print(f"  Evidence Hash: {report['evidence_hash'][:16]}...")
        print()
        print("Per-root results:")
        for root in ROOTS_24:
            status = result.root_results.get(root, "?")
            tag = "PASS" if status == "PASS" else status
            print(f"  [{tag}] {root}")
        if result.findings:
            print()
            for f in result.findings:
                tag = "FAIL" if f.severity == "deny" else f.severity.upper()
                print(f"  [{tag}] {f.check_id} | {f.root} | {f.path}")
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
