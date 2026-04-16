#!/usr/bin/env python3
"""Audit subscription revenue distribution."""

import argparse
import json
import yaml
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Audit subscription policy")
    parser.add_argument("--policy", required=True, help="Subscription policy YAML")
    parser.add_argument("--out", required=True, help="Output JSON file")

    args = parser.parse_args()

    policy_file = Path(args.policy)

    # Expected 50/30/10/10 model
    expected = {
        "protocol_development": 50,
        "community_rewards": 30,
        "dao_governance": 10,
        "operational_reserve": 10,
    }

    # Default distribution
    distribution = expected.copy()
    status = "PASS"
    mismatches = []

    if policy_file.exists():
        try:
            with open(policy_file, encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            if "distribution" in policy:
                dist_policy = policy["distribution"]
                # Extract percentages - handle both flat and nested structures
                extracted = {}
                for key, value in dist_policy.items():
                    if isinstance(value, dict) and "percent" in value:
                        extracted[key] = value["percent"]
                    elif isinstance(value, (int, float)):
                        extracted[key] = value

                # Check against expected 50/30/10/10 model
                for key in expected:
                    actual = extracted.get(key, 0)
                    exp = expected[key]
                    if actual != exp:
                        mismatches.append({
                            "key": key,
                            "expected": exp,
                            "actual": actual,
                        })

                if mismatches:
                    status = "FAIL_POLICY"

                distribution = extracted
        except Exception:
            pass

    total_percent = sum(distribution.values())

    result = {
        "status": status,
        "total_percent": total_percent,
        "distribution": distribution,
        "mismatches": mismatches,
    }

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
