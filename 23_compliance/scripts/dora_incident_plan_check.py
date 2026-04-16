#!/usr/bin/env python3
"""Check all 24 SSID roots for presence of docs/incident_response_plan.md."""

import argparse
import json
from pathlib import Path

CANONICAL_ROOTS = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto", "22_datasets",
    "23_compliance", "24_meta_orchestration",
]


def main():
    parser = argparse.ArgumentParser(description="Check DORA incident response plans")
    parser.add_argument("--repo-root", required=True, help="Repository root path")
    parser.add_argument("--roots", help="Specific roots to check (comma-separated)")
    parser.add_argument("--out", required=True, help="Output JSON file")
    parser.add_argument(
        "--doc-path",
        default="docs/incident_response_plan.md",
        help="Path to incident response plan within root"
    )

    args = parser.parse_args()

    repo_root = Path(args.repo_root)

    # Determine which roots to check
    if args.roots:
        roots_to_check = [r.strip() for r in args.roots.split(",")]
    else:
        roots_to_check = CANONICAL_ROOTS

    missing = []
    checks = []

    for root in roots_to_check:
        root_path = repo_root / root
        plan_path = root_path / args.doc_path

        check_result = {
            "root": root,
            "exists": plan_path.exists(),
            "path": str(plan_path),
        }
        checks.append(check_result)

        if not plan_path.exists():
            missing.append(root)

    status = "PASS" if not missing else "FAIL_DORA"

    result = {
        "status": status,
        "total_roots": len(roots_to_check),
        "missing": missing,
        "checks": checks,
    }

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 1 if missing else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
