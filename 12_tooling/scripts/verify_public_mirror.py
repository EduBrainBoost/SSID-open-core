#!/usr/bin/env python3
"""Verify public mirror structure and content."""
from __future__ import annotations

import sys
from pathlib import Path


EXPECTED_ROOTS = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto",
    "22_datasets", "23_compliance", "24_meta_orchestration",
]

REQUIRED_ROOT_FILES = {"README.md", "module.yaml"}

REQUIRED_ROOT_FILES = {"README.md", "module.yaml"}

REQUIRED_ROOT_FILES = {"README.md", "module.yaml"}


def verify_public_mirror(repo_root: Path | str = ".") -> dict:
    root = Path(repo_root)
    issues = []

    # Check 24 roots
    actual_roots = [d.name for d in root.iterdir() if d.is_dir() and d.name[0].isdigit()]
    for expected in EXPECTED_ROOTS:
        if expected not in actual_roots:
            issues.append(f"Missing root: {expected}")

    extra_roots = set(actual_roots) - set(EXPECTED_ROOTS)
    for extra in extra_roots:
        issues.append(f"Unexpected root: {extra}")

    # Check required files per root
    for root_name in EXPECTED_ROOTS:
        root_path = root / root_name
        if not root_path.exists():
            continue
        for required_file in REQUIRED_ROOT_FILES:
            if not (root_path / required_file).exists():
                issues.append(f"Missing {required_file} in {root_name}/")

    # Check required governance files
    for gov_file in ["README.md", "LICENSE", "SECURITY.md", "CODEOWNERS", ".gitignore"]:
        if not (root / gov_file).exists():
            issues.append(f"Missing governance file: {gov_file}")

    # Check CI workflows
    ci_path = root / ".github" / "workflows"
    if not ci_path.exists():
        issues.append("Missing .github/workflows/")
    else:
        workflows = list(ci_path.glob("*.yaml"))
        required_workflows = ["ci.yaml", "security.yaml", "scorecard.yaml", "release.yaml"]
        for wf in required_workflows:
            if not (ci_path / wf).exists():
                issues.append(f"Missing CI workflow: {wf}")

    # Check tooling scripts
    tooling_path = root / "12_tooling" / "scripts"
    if tooling_path.exists():
        required_scripts = [
            "build_audit_pack.py",
            "update_coverage_badge.py",
            "verify_public_mirror.py",
            "verify_export_manifest.py",
            "verify_private_leakage.py",
        ]
        for script in required_scripts:
            if not (tooling_path / script).exists():
                issues.append(f"Missing tooling script: {script}")
    else:
        issues.append("Missing 12_tooling/scripts/")

    # Check policy
    policy_path = root / "23_compliance" / "policies" / "opencore_policy.yaml"
    if not policy_path.exists():
        issues.append("Missing opencore_policy.yaml")

    # Check evidence and score
    if not (root / "23_compliance" / "evidence").exists():
        issues.append("Missing 23_compliance/evidence/")
    if not (root / "17_observability" / "score").exists():
        issues.append("Missing 17_observability/score/")

    # Check export registry
    registry_path = root / "24_meta_orchestration" / "registry" / "opencore_export_registry.json"
    if not registry_path.exists():
        issues.append("Missing opencore_export_registry.json")

    status = "PASS" if not issues else "FAIL"
    return {
        "status": status,
        "issues": issues,
        "roots_found": len(actual_roots),
        "roots_expected": len(EXPECTED_ROOTS),
    }


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    result = verify_public_mirror(repo)
    print(f"Status: {result['status']}")
    print(f"Roots: {result['roots_found']}/{result['roots_expected']}")
    for issue in result["issues"]:
        print(f"  - {issue}")
    sys.exit(0 if result["status"] == "PASS" else 1)
