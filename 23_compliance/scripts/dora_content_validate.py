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


def validate_plan_content(plan_file: Path) -> dict:
    """Validate incident response plan has required sections."""
    if not plan_file.exists():
        return {"valid": False, "reason": "File not found", "sections_found": []}

    content = plan_file.read_text().lower()

    sections_found = []
    for section in REQUIRED_SECTIONS:
        if section in content or section.replace("_", " ") in content:
            sections_found.append(section)

    valid = len(sections_found) >= 3  # At least 3 sections required

    return {
        "valid": valid,
        "sections_found": sections_found,
        "sections_missing": [s for s in REQUIRED_SECTIONS if s not in sections_found],
    }


def main():
    parser = argparse.ArgumentParser(description="Validate DORA plan content")
    parser.add_argument("--plan-file", required=True, help="Path to incident response plan")
    parser.add_argument("--out", required=True, help="Output JSON file")

    args = parser.parse_args()

    plan_file = Path(args.plan_file)
    result = validate_plan_content(plan_file)

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
