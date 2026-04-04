#!/usr/bin/env python3
"""AR-04: dora_incident_plan_check.py
Check all 24 SSID roots for presence of docs/incident_response_plan.md.
Exits 0 if all present; exits 1 if any root missing (FAIL_DORA).
"""

import argparse
import json
import sys
from datetime import UTC
from pathlib import Path

ALL_24_ROOTS = [
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


def check_roots(repo_root: Path, roots: list[str], required_file: str) -> dict:
    checks = {}
    missing = []
    present_but_empty = []
    compliant = 0

    for root_id in roots:
        plan_path = repo_root / root_id / required_file
        entry = {
            "path": str(Path(root_id) / required_file),
            "exists": plan_path.exists(),
            "size_bytes": 0,
            "sections_found": 0,
        }
        if plan_path.exists():
            content = plan_path.read_text(encoding="utf-8", errors="replace")
            size = len(plan_path.read_bytes())
            entry["size_bytes"] = size
            # Count markdown headings as sections
            sections = [ln for ln in content.splitlines() if ln.startswith("#")]
            entry["sections_found"] = len(sections)
            if size == 0:
                present_but_empty.append(root_id)
            else:
                compliant += 1
        else:
            missing.append(root_id)
        checks[root_id] = entry

    return {
        "total_roots": len(roots),
        "compliant": compliant,
        "missing": missing,
        "present_but_empty": present_but_empty,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DORA Incident Plan existence check")
    parser.add_argument(
        "--roots",
        nargs="+",
        default=ALL_24_ROOTS,
        help="Root directory IDs to check (default: all 24)",
    )
    parser.add_argument(
        "--required-file",
        default="docs/incident_response_plan.md",
        help="Required file path relative to each root",
    )
    parser.add_argument(
        "--template",
        default="05_documentation/templates/TEMPLATE_INCIDENT_RESPONSE.md",
        help="Template path (for reference in output)",
    )
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root directory (default: .)",
    )
    parser.add_argument("--ems-url", default="", help="EMS base URL for result reporting (optional)")
    parser.add_argument("--run-id", default="", help="Run ID for EMS reporting")
    parser.add_argument("--commit-sha", default="0" * 40, help="Commit SHA for EMS reporting")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    result = check_roots(repo_root, args.roots, args.required_file)
    result["template"] = args.template
    result["status"] = "PASS" if not result["missing"] and not result["present_but_empty"] else "FAIL_DORA"

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))

    print(
        f"DORA check: {result['compliant']}/{result['total_roots']} compliant, "
        f"missing={result['missing']}, status={result['status']}"
    )

    if args.ems_url:
        try:
            import os as _os
            import sys as _sys

            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "12_tooling"))
            from datetime import datetime as _dt

            from ssid_autorunner.ems_reporter import post_result

            post_result(
                ems_url=args.ems_url,
                ar_id="AR-04",
                run_id=args.run_id or f"CI-AR-04-{_dt.now(UTC).strftime('%Y%m%dT%H%M%S')}",
                result=result,
                commit_sha=args.commit_sha,
            )
        except (ImportError, Exception):
            pass  # ems_reporter optional — never block the gate

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
