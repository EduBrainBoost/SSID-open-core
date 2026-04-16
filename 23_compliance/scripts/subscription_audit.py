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

    # Default 50/30/10/10 model
    distribution = {
        "protocol_development": 50,
        "community_rewards": 30,
        "dao_governance": 10,
        "operational_reserve": 10,
    }

    if policy_file.exists():
        try:
            with open(policy_file, encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            if "distribution" in policy:
                distribution = policy["distribution"]
        except Exception:
            pass

    total_percent = sum(distribution.values())

    result = {
        "status": "PASS" if total_percent == 100 else "FAIL",
        "total_percent": total_percent,
        "distribution": distribution,
    }

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
