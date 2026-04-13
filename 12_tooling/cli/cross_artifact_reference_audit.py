#!/usr/bin/env python3
"""Cross-Artifact Reference Integrity Auditor — CC-SSID-SOT-XREF-01.

Cross-checks the 9 SoT (Source of Truth) artifacts that define SSID's
36 governance rules (SOT_AGENT_001 through SOT_AGENT_036) to ensure they
remain synchronized:

  1.  Artifact Existence:       all 9 SoT artifact paths exist on disk
  2.  Contract -> Validator:    every contract rule_id in validator RULES + PRIORITY
  3.  Contract -> Rego:         every contract rule_id has a deny clause in rego
  4.  Contract -> Tests:        every contract rule_id appears in test file
  5.  Rule Count Consistency:   contract, validator, rego all agree on count
  6.  Version Consistency:      version strings match across artifacts
  7.  Workflow Targets:         sot_autopilot.yml script references exist
  8.  Registry Integrity:       sot_registry.json hashes match disk
  9.  MoSCoW Report Rules:      enforcement report rule_ids exist in contract
  10. Diff Alert Artifacts:     SOT_DIFF_ALERT.json entries match registry

Exit codes:
  0 = PASS   — fully consistent
  1 = WARN   — advisory warnings only
  2 = FAIL   — hard consistency violations
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2

# The 9 SoT artifacts (relative to repo root)
SOT_ARTIFACTS: dict[str, str] = {
    "contract": "16_codex/contracts/sot/sot_contract.yaml",
    "rego": "23_compliance/policies/sot/sot_policy.rego",
    "validator_core": "03_core/validators/sot/sot_validator_core.py",
    "validator_cli": "12_tooling/cli/sot_validator.py",
    "tests": "11_test_simulation/tests_compliance/test_sot_validator.py",
    "moscow_report": "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md",
    "sot_registry": "24_meta_orchestration/registry/sot_registry.json",
    "workflow": ".github/workflows/sot_autopilot.yml",
    "diff_alert": "02_audit_logging/reports/SOT_DIFF_ALERT.json",
}

RULE_ID_PATTERN = re.compile(r"SOT_AGENT_\d{3}")


# -----------------------------------------------------------------------
# Finding / AuditResult (same pattern as registry_consistency_audit.py)
# -----------------------------------------------------------------------
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
        self.severity = severity  # "deny" | "warn"
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


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_rule_ids_from_text(text: str) -> list[str]:
    """Return all SOT_AGENT_NNN matches in text (preserving order)."""
    return RULE_ID_PATTERN.findall(text)


def extract_unique_rule_ids_from_text(text: str) -> set[str]:
    """Return unique SOT_AGENT_NNN matches in text."""
    return set(RULE_ID_PATTERN.findall(text))


# -----------------------------------------------------------------------
# Rule ID extractors per artifact type
# -----------------------------------------------------------------------
def extract_contract_rules(path: Path) -> tuple[list[str], str | None]:
    """Extract rule IDs and version from sot_contract.yaml.

    Returns (list_of_rule_ids, version_or_None).
    """
    data = load_yaml(path)
    version = data.get("version") if isinstance(data, dict) else None
    rules_list = data.get("rules", []) if isinstance(data, dict) else []
    rule_ids: list[str] = []
    for rule in rules_list:
        if isinstance(rule, dict) and "id" in rule:
            rule_ids.append(rule["id"])
    return rule_ids, str(version) if version else None


def extract_validator_rules(path: Path) -> tuple[set[str], list[str], str | None]:
    """Extract RULES dict keys, PRIORITY list items, and version from validator_core.py.

    Returns (rules_dict_keys, priority_list_items, version_or_None).
    """
    text = read_text(path)

    # Extract RULES dict keys: "SOT_AGENT_NNN" as dict keys
    rules_keys: set[str] = set()
    # Match keys in a dict-like context: "SOT_AGENT_NNN":
    for m in re.finditer(r'"(SOT_AGENT_\d{3})"\s*:', text):
        rules_keys.add(m.group(1))

    # Extract PRIORITY list items
    priority_items: list[str] = []
    priority_match = re.search(r'PRIORITY\s*=\s*\[([^\]]*)\]', text, re.DOTALL)
    if priority_match:
        priority_block = priority_match.group(1)
        for m in re.finditer(r'"(SOT_AGENT_\d{3})"', priority_block):
            priority_items.append(m.group(1))

    # Extract version from comment or variable
    version = None
    ver_match = re.search(r'(?:VERSION|__version__)\s*=\s*["\']([^"\']+)["\']', text)
    if ver_match:
        version = ver_match.group(1)
    else:
        ver_match = re.search(r'#.*\bv(\d+\.\d+(?:\.\d+)?)\b', text)
        if ver_match:
            version = ver_match.group(1)

    return rules_keys, priority_items, version


def extract_rego_rule_ids(path: Path) -> tuple[set[str], str | None]:
    """Extract unique rule IDs from deny blocks and version from sot_policy.rego.

    Returns (set_of_rule_ids, version_or_None).
    """
    text = read_text(path)

    # Find all SOT_AGENT_NNN references in deny blocks
    rule_ids = extract_unique_rule_ids_from_text(text)

    # Extract version from comment
    version = None
    ver_match = re.search(r'#.*\bv(\d+\.\d+(?:\.\d+)?)\b', text)
    if ver_match:
        version = ver_match.group(1)

    return rule_ids, version


# -----------------------------------------------------------------------
# Check 1: Artifact Existence
# -----------------------------------------------------------------------
def check_artifact_existence(
    repo: Path,
    result: AuditResult,
) -> set[str]:
    """Verify all 9 SoT artifact paths exist. Returns set of missing artifact keys."""
    missing: set[str] = set()
    for key, rel_path in SOT_ARTIFACTS.items():
        full_path = repo / rel_path
        if not full_path.exists():
            result.add(Finding(
                "reference_missing",
                "deny",
                rel_path,
                f"SoT artifact '{key}' does not exist on disk",
            ))
            missing.add(key)
    return missing


# -----------------------------------------------------------------------
# Check 2: Contract -> Validator rule mapping
# -----------------------------------------------------------------------
def check_contract_to_validator(
    contract_rules: list[str],
    validator_rules: set[str],
    validator_priority: list[str],
    result: AuditResult,
) -> None:
    contract_path = SOT_ARTIFACTS["contract"]
    validator_path = SOT_ARTIFACTS["validator_core"]

    for rule_id in contract_rules:
        if rule_id not in validator_rules:
            result.add(Finding(
                "rule_unmapped",
                "deny",
                validator_path,
                f"rule '{rule_id}' in contract but missing from validator RULES dict",
            ))
        if rule_id not in validator_priority:
            result.add(Finding(
                "rule_unmapped",
                "deny",
                validator_path,
                f"rule '{rule_id}' in contract but missing from validator PRIORITY list",
            ))

    # Reverse: validator rules not in contract
    contract_set = set(contract_rules)
    for rule_id in sorted(validator_rules - contract_set):
        result.add(Finding(
            "rule_unmapped",
            "deny",
            contract_path,
            f"rule '{rule_id}' in validator RULES but missing from contract",
        ))
    for rule_id in validator_priority:
        if rule_id not in contract_set:
            result.add(Finding(
                "rule_unmapped",
                "deny",
                contract_path,
                f"rule '{rule_id}' in validator PRIORITY but missing from contract",
            ))


# -----------------------------------------------------------------------
# Check 3: Contract -> Rego rule mapping
# -----------------------------------------------------------------------
def check_contract_to_rego(
    contract_rules: list[str],
    rego_rules: set[str],
    result: AuditResult,
) -> None:
    contract_path = SOT_ARTIFACTS["contract"]
    rego_path = SOT_ARTIFACTS["rego"]

    for rule_id in contract_rules:
        if rule_id not in rego_rules:
            result.add(Finding(
                "rule_unmapped",
                "deny",
                rego_path,
                f"rule '{rule_id}' in contract but no deny clause in rego policy",
            ))

    # Reverse: rego rules not in contract
    contract_set = set(contract_rules)
    for rule_id in sorted(rego_rules - contract_set):
        result.add(Finding(
            "rule_unmapped",
            "deny",
            contract_path,
            f"rule '{rule_id}' in rego policy but missing from contract",
        ))


# -----------------------------------------------------------------------
# Check 4: Contract -> Tests coverage
# -----------------------------------------------------------------------
def check_contract_to_tests(
    contract_rules: list[str],
    test_rule_ids: set[str],
    result: AuditResult,
) -> None:
    for rule_id in contract_rules:
        if rule_id not in test_rule_ids:
            result.add(Finding(
                "test_coverage_gap",
                "warn",
                SOT_ARTIFACTS["tests"],
                f"rule '{rule_id}' in contract but not referenced in test file",
            ))


# -----------------------------------------------------------------------
# Check 5: Rule count consistency
# -----------------------------------------------------------------------
def check_rule_count_consistency(
    contract_rules: list[str],
    validator_rules: set[str],
    validator_priority: list[str],
    rego_rules: set[str],
    result: AuditResult,
) -> None:
    counts = {
        "contract": len(contract_rules),
        "validator_RULES": len(validator_rules),
        "validator_PRIORITY": len(validator_priority),
        "rego_deny": len(rego_rules),
    }

    unique_counts = set(counts.values())
    if len(unique_counts) > 1:
        detail_parts = [f"{k}={v}" for k, v in counts.items()]
        result.add(Finding(
            "rule_count_drift",
            "deny",
            "cross-artifact",
            f"rule count mismatch across artifacts: {', '.join(detail_parts)}",
        ))

    # Check for duplicates within contract
    seen: set[str] = set()
    for rule_id in contract_rules:
        if rule_id in seen:
            result.add(Finding(
                "rule_duplicate",
                "deny",
                SOT_ARTIFACTS["contract"],
                f"duplicate rule_id '{rule_id}' in contract",
            ))
        seen.add(rule_id)

    # Check for duplicates within priority list
    seen_priority: set[str] = set()
    for rule_id in validator_priority:
        if rule_id in seen_priority:
            result.add(Finding(
                "rule_duplicate",
                "deny",
                SOT_ARTIFACTS["validator_core"],
                f"duplicate rule_id '{rule_id}' in validator PRIORITY list",
            ))
        seen_priority.add(rule_id)


# -----------------------------------------------------------------------
# Check 6: Version consistency
# -----------------------------------------------------------------------
def check_version_consistency(
    contract_version: str | None,
    validator_version: str | None,
    rego_version: str | None,
    result: AuditResult,
) -> None:
    versions: dict[str, str] = {}
    if contract_version:
        versions["contract"] = contract_version
    if validator_version:
        versions["validator_core"] = validator_version
    if rego_version:
        versions["rego"] = rego_version

    if len(versions) < 2:
        return  # not enough versions to compare

    unique_versions = set(versions.values())
    if len(unique_versions) > 1:
        detail_parts = [f"{k}={v}" for k, v in versions.items()]
        result.add(Finding(
            "version_drift",
            "warn",
            "cross-artifact",
            f"version mismatch across artifacts: {', '.join(detail_parts)}",
        ))


# -----------------------------------------------------------------------
# Check 7: Workflow targets
# -----------------------------------------------------------------------
def check_workflow_targets(
    repo: Path,
    result: AuditResult,
) -> None:
    workflow_path = repo / SOT_ARTIFACTS["workflow"]
    if not workflow_path.exists():
        return  # already reported in artifact existence check

    text = read_text(workflow_path)

    # Extract python and pytest command targets
    script_refs: list[str] = []
    for m in re.finditer(r'\bpython\s+([\w/.\_-]+\.py)', text):
        script_refs.append(m.group(1))
    for m in re.finditer(r'\bpytest\s+([\w/.\_-]+(?:\.py)?)', text):
        script_refs.append(m.group(1))

    for ref in script_refs:
        full_path = repo / ref
        if not full_path.exists():
            result.add(Finding(
                "workflow_target_missing",
                "deny",
                SOT_ARTIFACTS["workflow"],
                f"workflow references script '{ref}' which does not exist",
            ))


# -----------------------------------------------------------------------
# Check 8: Registry integrity (sot_registry.json hash verification)
# -----------------------------------------------------------------------
def check_registry_integrity(
    repo: Path,
    result: AuditResult,
) -> dict[str, str]:
    """Verify sot_registry.json artifact hashes. Returns dict of artifact name->path."""
    registry_path = repo / SOT_ARTIFACTS["sot_registry"]
    if not registry_path.exists():
        return {}

    try:
        data = load_json(registry_path)
    except Exception:
        result.add(Finding(
            "reference_broken",
            "deny",
            SOT_ARTIFACTS["sot_registry"],
            "sot_registry.json is not valid JSON",
        ))
        return {}

    artifacts = data.get("roots", {}).get("sot_artifacts", [])
    registry_artifacts: dict[str, str] = {}

    for artifact in artifacts:
        name = artifact.get("name", "?")
        path = artifact.get("path", "")
        expected_hash = artifact.get("hash_sha256", "")

        registry_artifacts[name] = path
        full_path = repo / path

        if not full_path.exists():
            result.add(Finding(
                "reference_broken",
                "deny",
                path,
                f"sot_registry artifact '{name}' points to non-existent file",
            ))
            continue

        if expected_hash:
            actual_hash = sha256_file(full_path)
            if actual_hash != expected_hash:
                result.add(Finding(
                    "registry_reference_stale",
                    "warn",
                    path,
                    f"sot_registry artifact '{name}' hash mismatch: "
                    f"expected={expected_hash[:16]}..., actual={actual_hash[:16]}...",
                ))

    return registry_artifacts


# -----------------------------------------------------------------------
# Check 9: MoSCoW report rules
# -----------------------------------------------------------------------
def check_moscow_report(
    repo: Path,
    contract_rules_set: set[str],
    result: AuditResult,
) -> None:
    report_path = repo / SOT_ARTIFACTS["moscow_report"]
    if not report_path.exists():
        return  # already reported in artifact existence check

    text = read_text(report_path)
    report_rule_ids = extract_unique_rule_ids_from_text(text)

    for rule_id in sorted(report_rule_ids - contract_rules_set):
        result.add(Finding(
            "rule_unmapped",
            "warn",
            SOT_ARTIFACTS["moscow_report"],
            f"rule '{rule_id}' in MoSCoW report but missing from contract",
        ))

    for rule_id in sorted(contract_rules_set - report_rule_ids):
        result.add(Finding(
            "rule_unmapped",
            "warn",
            SOT_ARTIFACTS["moscow_report"],
            f"rule '{rule_id}' in contract but not listed in MoSCoW report",
        ))


# -----------------------------------------------------------------------
# Check 10: Diff alert artifacts
# -----------------------------------------------------------------------
def check_diff_alert(
    repo: Path,
    registry_artifacts: dict[str, str],
    result: AuditResult,
) -> None:
    diff_alert_path = repo / SOT_ARTIFACTS["diff_alert"]
    if not diff_alert_path.exists():
        return  # already reported in artifact existence check

    try:
        data = load_json(diff_alert_path)
    except Exception:
        result.add(Finding(
            "reference_broken",
            "deny",
            SOT_ARTIFACTS["diff_alert"],
            "SOT_DIFF_ALERT.json is not valid JSON",
        ))
        return

    # Extract artifact names/paths from diff_alert and cross-check with registry
    alert_artifacts = data.get("artifacts", [])
    if not isinstance(alert_artifacts, list):
        alert_artifacts = []

    registry_paths = set(registry_artifacts.values())

    for entry in alert_artifacts:
        if isinstance(entry, dict):
            path = entry.get("path", "")
            name = entry.get("name", path)
        elif isinstance(entry, str):
            path = entry
            name = entry
        else:
            continue

        if path and registry_paths and path not in registry_paths:
            result.add(Finding(
                "reference_broken",
                "deny",
                SOT_ARTIFACTS["diff_alert"],
                f"diff_alert artifact '{name}' (path='{path}') "
                f"not found in sot_registry.json",
            ))


# -----------------------------------------------------------------------
# Main audit
# -----------------------------------------------------------------------
def run_audit(repo: Path) -> AuditResult:
    result = AuditResult()

    # Check 1: Artifact existence
    missing = check_artifact_existence(repo, result)

    # Extract data from available artifacts
    contract_rules: list[str] = []
    contract_version: str | None = None
    validator_rules: set[str] = set()
    validator_priority: list[str] = []
    validator_version: str | None = None
    rego_rules: set[str] = set()
    rego_version: str | None = None
    test_rule_ids: set[str] = set()

    if "contract" not in missing:
        try:
            contract_rules, contract_version = extract_contract_rules(
                repo / SOT_ARTIFACTS["contract"]
            )
        except Exception as exc:
            result.add(Finding(
                "reference_broken",
                "deny",
                SOT_ARTIFACTS["contract"],
                f"cannot parse contract YAML: {exc}",
            ))

    if "validator_core" not in missing:
        try:
            validator_rules, validator_priority, validator_version = (
                extract_validator_rules(repo / SOT_ARTIFACTS["validator_core"])
            )
        except Exception as exc:
            result.add(Finding(
                "reference_broken",
                "deny",
                SOT_ARTIFACTS["validator_core"],
                f"cannot parse validator_core.py: {exc}",
            ))

    if "rego" not in missing:
        try:
            rego_rules, rego_version = extract_rego_rule_ids(
                repo / SOT_ARTIFACTS["rego"]
            )
        except Exception as exc:
            result.add(Finding(
                "reference_broken",
                "deny",
                SOT_ARTIFACTS["rego"],
                f"cannot parse rego policy: {exc}",
            ))

    if "tests" not in missing:
        try:
            test_text = read_text(repo / SOT_ARTIFACTS["tests"])
            test_rule_ids = extract_unique_rule_ids_from_text(test_text)
        except Exception as exc:
            result.add(Finding(
                "reference_broken",
                "deny",
                SOT_ARTIFACTS["tests"],
                f"cannot read test file: {exc}",
            ))

    # Checks 2-6 require contract rules
    contract_rules_set = set(contract_rules)

    if contract_rules and validator_rules:
        # Check 2: Contract -> Validator
        check_contract_to_validator(
            contract_rules, validator_rules, validator_priority, result
        )

    if contract_rules and rego_rules:
        # Check 3: Contract -> Rego
        check_contract_to_rego(contract_rules, rego_rules, result)

    if contract_rules and test_rule_ids:
        # Check 4: Contract -> Tests
        check_contract_to_tests(contract_rules, test_rule_ids, result)

    if contract_rules or validator_rules or rego_rules:
        # Check 5: Rule count consistency
        check_rule_count_consistency(
            contract_rules, validator_rules, validator_priority, rego_rules, result
        )

    # Check 6: Version consistency
    check_version_consistency(
        contract_version, validator_version, rego_version, result
    )

    # Check 7: Workflow targets
    if "workflow" not in missing:
        check_workflow_targets(repo, result)

    # Check 8: Registry integrity
    registry_artifacts: dict[str, str] = {}
    if "sot_registry" not in missing:
        registry_artifacts = check_registry_integrity(repo, result)

    # Check 9: MoSCoW report rules
    if "moscow_report" not in missing and contract_rules:
        check_moscow_report(repo, contract_rules_set, result)

    # Check 10: Diff alert artifacts
    if "diff_alert" not in missing:
        check_diff_alert(repo, registry_artifacts, result)

    return result


def generate_report(result: AuditResult, repo: Path) -> dict[str, Any]:
    ts = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return {
        "audit_type": "cross_artifact_reference",
        "timestamp_utc": ts,
        "repo": str(repo),
        "overall": result.overall,
        "finding_count": len(result.findings),
        "deny_count": sum(1 for f in result.findings if f.severity == "deny"),
        "warn_count": sum(1 for f in result.findings if f.severity == "warn"),
        "evidence_hash": result.evidence_hash(),
        "findings": [f.to_dict() for f in result.findings],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cross_artifact_reference_audit.py",
        description="Audit cross-artifact reference integrity for SSID SoT rules.",
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
        print(f"Cross-Artifact Reference Audit: {result.overall}")
        print(f"  Findings: {len(result.findings)} "
              f"(deny={report['deny_count']}, warn={report['warn_count']})")
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
