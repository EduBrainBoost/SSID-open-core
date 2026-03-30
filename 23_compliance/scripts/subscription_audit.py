#!/usr/bin/env python3
"""AR-10: subscription_audit.py
Validates subscription revenue distribution sums to exactly 100%
with the 50/30/10/10 model per SoT.
Exits 0 (PASS) or 1 (FAIL_POLICY).
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

EXPECTED_DISTRIBUTION = {
    "protocol_development": 50,
    "community_rewards": 30,
    "dao_governance": 10,
    "operational_reserve": 10,
}
EXPECTED_SUM = 100


def audit_subscription(policy: dict) -> dict:
    distribution = policy.get("distribution", {})
    total = sum(v.get("percent", 0) for v in distribution.values())
    expected_sum = policy.get("sum_must_equal", EXPECTED_SUM)

    mismatches = []
    for key, expected_pct in EXPECTED_DISTRIBUTION.items():
        actual = distribution.get(key, {}).get("percent")
        if actual != expected_pct:
            mismatches.append({
                "key": key,
                "expected": expected_pct,
                "actual": actual,
            })

    sum_correct = total == expected_sum
    model_correct = len(mismatches) == 0
    status = "PASS" if sum_correct and model_correct else "FAIL_POLICY"

    return {
        "status": status,
        "total_percent": total,
        "expected_sum": expected_sum,
        "sum_correct": sum_correct,
        "model_correct": model_correct,
        "mismatches": mismatches,
        "distribution": {k: v.get("percent") for k, v in distribution.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Subscription revenue 50/30/10/10 audit")
    parser.add_argument("--policy", required=True, help="subscription_revenue_policy.yaml")
    parser.add_argument("--implementation", help="subscription_revenue_distributor.py (ref)")
    parser.add_argument("--out", required=True, help="Output JSON")
    args = parser.parse_args()

    if not HAS_YAML:
        print("ERROR: pyyaml required", file=sys.stderr)
        sys.exit(2)

    policy = yaml.safe_load(Path(args.policy).read_text())
    result = audit_subscription(policy)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(
        f"Subscription audit: status={result['status']}, "
        f"sum={result['total_percent']}% (expected 100%)"
    )

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
