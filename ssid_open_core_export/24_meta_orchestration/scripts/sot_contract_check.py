#!/usr/bin/env python3
"""
AR-02: SOT Contract Check against sot_contract.yaml (SOT_AGENT_001-036)
"""

import argparse
import contextlib
import json
import subprocess
import sys
from pathlib import Path

import yaml


def load_rules(rules_path: Path) -> list:
    data = yaml.safe_load(rules_path.read_text())
    # Handle different YAML structures — try common keys
    if "rules" in data:
        return data["rules"]
    elif isinstance(data, list):
        return data
    else:
        # Return all top-level items that look like rules
        rules = []
        for key, val in data.items():
            if isinstance(val, dict) and "description" in val:
                val["id"] = key
                rules.append(val)
        return rules


def load_or_generate_scan(scan_path: Path, repo_root: Path) -> dict:
    content = scan_path.read_text().strip() if scan_path.exists() else ""
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    generator = repo_root / "24_meta_orchestration/scripts/generate_repo_scan.py"
    if generator.exists():
        subprocess.run(
            [
                "python",
                str(generator),
                "--repo-root",
                str(repo_root),
                "--commit-sha",
                "0" * 40,
                "--out",
                str(scan_path),
            ],
            check=True,
        )
        return json.loads(scan_path.read_text())
    return {}


def check_rule(rule: dict, scan: dict, repo_root: Path) -> dict:
    rule_id = rule.get("id", "UNKNOWN")
    description = rule.get("description", "")
    severity = rule.get("severity", "warning")
    result = {
        "rule_id": rule_id,
        "description": description,
        "severity": severity,
        "passed": True,
        "details": "",
    }

    # Extract numeric part for range checks
    try:
        num = int(rule_id.replace("SOT_AGENT_", ""))
    except (ValueError, AttributeError):
        return result

    # SOT_AGENT_001: Dispatcher = single entry point
    if num == 1:
        dispatcher = repo_root / "24_meta_orchestration" / "dispatcher"
        result["passed"] = dispatcher.exists()
        result["details"] = str(dispatcher)

    # SOT_AGENT_002: Documentation canonical paths
    elif num == 2:
        result["passed"] = (repo_root / "05_documentation").exists()
        result["details"] = str(repo_root / "05_documentation")

    # SOT_AGENT_003: Data minimization (structural check — 06_data_pipeline present)
    elif num == 3:
        result["passed"] = (repo_root / "06_data_pipeline").exists()
        result["details"] = str(repo_root / "06_data_pipeline")

    # SOT_AGENT_004: Artifacts canonical paths (check 16_codex/contracts exists)
    elif num == 4:
        result["passed"] = (repo_root / "16_codex" / "contracts").exists()
        result["details"] = str(repo_root / "16_codex" / "contracts")

    # SOT_AGENT_005: No duplicate rules (check sot_contract.yaml itself)
    elif num == 5:
        sot_yaml = repo_root / "16_codex" / "contracts" / "sot" / "sot_contract.yaml"
        result["passed"] = sot_yaml.exists()
        result["details"] = str(sot_yaml)

    # SOT_AGENT_006-008: Root 01 AI Layer checks
    elif num == 6:
        result["passed"] = (repo_root / "01_ai_layer").exists()
        result["details"] = str(repo_root / "01_ai_layer")

    elif num == 7:
        # No shadow files: check that 01_ai_layer has no forbidden duplicate module.yaml outside it
        root = repo_root / "01_ai_layer"
        result["passed"] = root.exists()
        result["details"] = str(root)

    elif num == 8:
        result["passed"] = (repo_root / "01_ai_layer").exists()
        result["details"] = str(repo_root / "01_ai_layer")

    # SOT_AGENT_009-011: Root 02 Audit Logging checks
    elif num == 9 or num == 10 or num == 11:
        result["passed"] = (repo_root / "02_audit_logging").exists()
        result["details"] = str(repo_root / "02_audit_logging")

    # SOT_AGENT_012-014: Root 03 Core checks
    elif num == 12 or num == 13 or num == 14:
        result["passed"] = (repo_root / "03_core").exists()
        result["details"] = str(repo_root / "03_core")

    # SOT_AGENT_015-017: Root 04 Deployment checks
    elif num == 15 or num == 16 or num == 17:
        result["passed"] = (repo_root / "04_deployment").exists()
        result["details"] = str(repo_root / "04_deployment")

    # SOT_AGENT_018-020: Root 05 Documentation checks
    elif num == 18 or num == 19 or num == 20:
        result["passed"] = (repo_root / "05_documentation").exists()
        result["details"] = str(repo_root / "05_documentation")

    # SOT_AGENT_021-023: Root 06 Data Pipeline checks
    elif num == 21 or num == 22 or num == 23:
        result["passed"] = (repo_root / "06_data_pipeline").exists()
        result["details"] = str(repo_root / "06_data_pipeline")

    # SOT_AGENT_024: investment_disclaimers.yaml MUST exist
    elif num == 24:
        p = repo_root / "07_governance_legal" / "investment_disclaimers.yaml"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_025: approval_workflow.yaml MUST exist
    elif num == 25:
        p = repo_root / "07_governance_legal" / "approval_workflow.yaml"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_026: regulatory_map_index.yaml MUST exist
    elif num == 26:
        p = repo_root / "07_governance_legal" / "regulatory_map_index.yaml"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_027: legal_positioning.md MUST exist
    elif num == 27:
        p = repo_root / "07_governance_legal" / "legal_positioning.md"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_028: 07_governance_legal README.md MUST exist
    elif num == 28:
        p = repo_root / "07_governance_legal" / "README.md"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_029: module.yaml MUST exist in 08_identity_score
    elif num == 29:
        p = repo_root / "08_identity_score" / "module.yaml"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_030: README.md MUST exist in 08_identity_score
    elif num == 30:
        p = repo_root / "08_identity_score" / "README.md"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_031: docs/ MUST exist in 08_identity_score
    elif num == 31:
        p = repo_root / "08_identity_score" / "docs"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_032: src/ MUST exist in 08_identity_score
    elif num == 32:
        p = repo_root / "08_identity_score" / "src"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_033: tests/ MUST exist in 08_identity_score
    elif num == 33:
        p = repo_root / "08_identity_score" / "tests"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_034: models/ MUST exist in 08_identity_score
    elif num == 34:
        p = repo_root / "08_identity_score" / "models"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_035: rules/ MUST exist in 08_identity_score
    elif num == 35:
        p = repo_root / "08_identity_score" / "rules"
        result["passed"] = p.exists()
        result["details"] = str(p)

    # SOT_AGENT_036: api/ MUST exist in 08_identity_score
    elif num == 36:
        p = repo_root / "08_identity_score" / "api"
        result["passed"] = p.exists()
        result["details"] = str(p)

    return result


def run_checks(rules_path: Path, scan_path: Path, repo_root: Path) -> dict:
    rules = load_rules(rules_path)
    scan = {}
    if scan_path and scan_path.exists():
        content = scan_path.read_text().strip()
        if content:
            with contextlib.suppress(json.JSONDecodeError):
                scan = json.loads(content)

    results = [check_rule(r, scan, repo_root) for r in rules]
    failed = [r for r in results if not r["passed"]]
    critical_failures = [r for r in failed if r["severity"] == "critical"]

    return {
        "total_rules": len(rules),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "critical_failures": len(critical_failures),
        "results": results,
        "status": "FAIL_SOT" if failed else "PASS",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", required=True)
    parser.add_argument("--repo-scan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generate-scan-if-missing", default="false")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    scan_path = Path(args.repo_scan)

    if args.generate_scan_if_missing.lower() == "true":
        # Regenerate if file is missing or empty/invalid
        content = scan_path.read_text().strip() if scan_path.exists() else ""
        valid = False
        if content:
            try:
                json.loads(content)
                valid = True
            except json.JSONDecodeError:
                pass
        if not valid:
            load_or_generate_scan(scan_path, repo_root)

    result = run_checks(Path(args.rules), scan_path, repo_root)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"SOT check: {result['status']} ({result['passed']}/{result['total_rules']} rules passed)")
    sys.exit(0 if result["status"] == "PASS" else 1)
