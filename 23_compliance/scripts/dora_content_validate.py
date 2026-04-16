#!/usr/bin/env python3
"""Validate DORA incident response plan content."""

import argparse
import json
from pathlib import Path


REQUIRED_SECTIONS = [
    "detection",
    "escalation",
    "mitigation",
    "recovery",
    "post_mortem",
]


def validate_plan_content(plan_file: Path, min_sections: int = 3) -> dict:
    """Validate incident response plan has required sections."""
    if not plan_file.exists():
        return {"valid": False, "reason": "File not found", "sections_found": []}

    content = plan_file.read_text().lower()

    sections_found = []
    for section in REQUIRED_SECTIONS:
        if section in content or section.replace("_", " ") in content:
            sections_found.append(section)

    valid = len(sections_found) >= min_sections

    return {
        "valid": valid,
        "sections_found": sections_found,
        "sections_missing": [s for s in REQUIRED_SECTIONS if s not in sections_found],
    }


def main():
    parser = argparse.ArgumentParser(description="Validate DORA plan content")
    parser.add_argument("--plan-file", required=False, help="Path to incident response plan")
    parser.add_argument("--results", required=False, help="Results file from dora_incident_plan_check.py")
    parser.add_argument("--min-sections", type=int, default=3, help="Minimum required sections")
    parser.add_argument("--repo-root", required=False, help="Repository root")
    parser.add_argument("--source", required=False, help="Source information")
    parser.add_argument("--out", required=True, help="Output JSON file")

    args = parser.parse_args()
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()

    # If --results provided, validate from check results
    if args.results:
        results_file = Path(args.results)
        check_results = json.loads(results_file.read_text())

        fail_policy_roots = []
        compliant_count = 0

        for check in check_results.get("checks", []):
            if check["exists"]:
                # Read the plan file and validate content
                plan_path = repo_root / check["root"] / "docs" / "incident_response_plan.md"
                if plan_path.exists():
                    content = plan_path.read_text().lower()
                    sections_found = 0
                    for section in REQUIRED_SECTIONS:
                        if section in content or section.replace("_", " ") in content:
                            sections_found += 1

                    if sections_found >= args.min_sections:
                        compliant_count += 1
                    else:
                        fail_policy_roots.append(check["root"])
                else:
                    fail_policy_roots.append(check["root"])

        status = "PASS" if not fail_policy_roots else "FAIL_POLICY"
        result = {
            "status": status,
            "compliant": compliant_count,
            "fail_policy_roots": fail_policy_roots,
        }
    else:
        # Legacy single plan validation
        plan_file = Path(args.plan_file) if args.plan_file else None
        if not plan_file:
            return 1
        result = validate_plan_content(plan_file, args.min_sections)

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    if args.results:
        return 0 if result["status"] == "PASS" else 1
    else:
        return 0 if result.get("valid", True) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
