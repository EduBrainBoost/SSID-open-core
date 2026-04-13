#!/usr/bin/env python3
"""AR-04: dora_content_validate.py
Validate content quality of incident response plans.
Checks: minimum section count, non-empty content.
"""

import argparse
import json
import sys
from pathlib import Path


def validate_content(dora_results: dict, repo_root: Path, min_sections: int) -> dict:
    checks = dora_results.get("checks", {})
    validation_results = {}
    fail_policy = []

    for root_id, info in checks.items():
        if not info["exists"]:
            # Missing files are already FAIL_DORA — not re-evaluated here
            validation_results[root_id] = {"status": "SKIP_MISSING"}
            continue

        plan_path = repo_root / info["path"]
        if not plan_path.exists():
            validation_results[root_id] = {"status": "SKIP_MISSING"}
            continue

        content = plan_path.read_text(encoding="utf-8", errors="replace").strip()
        size = len(content)
        sections = [ln for ln in content.splitlines() if ln.startswith("#")]
        section_count = len(sections)

        if size == 0:
            status = "FAIL_POLICY"
            reason = "empty file"
            fail_policy.append(root_id)
        elif section_count < min_sections:
            status = "FAIL_POLICY"
            reason = f"only {section_count} sections (min={min_sections})"
            fail_policy.append(root_id)
        else:
            status = "PASS"
            reason = f"{section_count} sections found"

        validation_results[root_id] = {
            "status": status,
            "reason": reason,
            "size_bytes": size,
            "sections_found": section_count,
        }

    overall = "PASS" if not fail_policy else "FAIL_POLICY"
    return {
        "status": overall,
        "fail_policy_roots": fail_policy,
        "min_sections_required": min_sections,
        "results": validation_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate DORA incident plan content")
    parser.add_argument("--results", required=True, help="Path to dora_check_results.json")
    parser.add_argument("--min-sections", type=int, default=5, help="Minimum # sections")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--repo-root", default=".", help="Repo root directory")
    args = parser.parse_args()

    dora_results = json.loads(Path(args.results).read_text())
    repo_root = Path(args.repo_root)
    result = validate_content(dora_results, repo_root, args.min_sections)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(f"DORA content validation: status={result['status']}, fail_policy={result['fail_policy_roots']}")

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
