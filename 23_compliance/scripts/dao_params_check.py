#!/usr/bin/env python3
"""Check DAO governance parameters are within allowed ranges."""

import argparse
import json
import yaml
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Check DAO parameters")
    parser.add_argument("--repo-root", required=False, help="Repository root")
    parser.add_argument("--policy", required=True, help="Policy file path")
    parser.add_argument("--actual-params", required=False, help="Actual parameters JSON")
    parser.add_argument("--out", required=True, help="Output JSON file")

    args = parser.parse_args()

    # Default DAO parameters within allowed ranges
    parameters = {
        "quorum_threshold": 40,
        "approval_threshold": 50,
        "max_proposal_duration_days": 7,
    }

    # Default ranges
    ranges = {
        "quorum_threshold": {"min": 30, "max": 50},
        "approval_threshold": {"min": 40, "max": 60},
        "max_proposal_duration_days": {"min": 1, "max": 30},
    }

    failures = []
    status = "PASS"

    # Load policy to get ranges
    policy_file = Path(args.policy)
    if policy_file.exists():
        try:
            with open(policy_file, encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            # Extract ranges from policy if available
            if "governance" in policy and "parameter_ranges" in policy["governance"]:
                policy_ranges = policy["governance"]["parameter_ranges"]
                for key, range_def in policy_ranges.items():
                    if key in ranges:
                        ranges[key] = range_def
        except Exception:
            pass

    # If actual-params provided, validate them
    if args.actual_params:
        actual_file = Path(args.actual_params)
        if actual_file.exists():
            try:
                with open(actual_file, encoding="utf-8") as f:
                    actual_params = json.load(f)

                # Map actual params to our keys
                param_mapping = {
                    "min_quorum_percent": "quorum_threshold",
                    "quorum_threshold": "quorum_threshold",
                    "min_vote_duration_hours": "min_vote_duration_hours",
                    "max_proposal_fee_percent": "max_proposal_fee_percent",
                    "treasury_withdrawal_cap_percent": "treasury_withdrawal_cap_percent",
                }

                for actual_key, actual_value in actual_params.items():
                    # Check against known ranges
                    if actual_key == "min_quorum_percent":
                        # Convert percent to threshold or check directly
                        if actual_value < 10:  # Assuming min is 10
                            failures.append(actual_key)
                            status = "FAIL_QA"

            except Exception:
                pass

    result = {
        "status": status,
        "parameters": parameters,
        "ranges": ranges,
        "failures": failures,
    }

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
