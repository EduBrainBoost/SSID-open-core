#!/usr/bin/env python3
"""subscription_simulate.py -- CLI tool to simulate subscription revenue distribution.

Usage: python 12_tooling/cli/subscription_simulate.py --plan basic --period monthly --amount 29.99
"""
import argparse
import json
import sys


PLANS = {
    "basic": {"platform_pct": 30, "creator_pct": 60, "validator_pct": 10},
    "pro": {"platform_pct": 25, "creator_pct": 65, "validator_pct": 10},
    "enterprise": {"platform_pct": 20, "creator_pct": 70, "validator_pct": 10},
}


def simulate(plan: str, period: str, amount: float) -> dict:
    """Simulate subscription revenue distribution."""
    if plan not in PLANS:
        raise ValueError(f"Unknown plan: {plan}. Available: {list(PLANS.keys())}")
    split = PLANS[plan]
    dist = {k.replace("_pct", ""): round(amount * v / 100.0, 2) for k, v in split.items()}
    return {
        "plan": plan,
        "period": period,
        "gross_amount": amount,
        "distribution": dist,
        "invariant_sum_check": sum(dist.values()) == amount,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate subscription revenue")
    parser.add_argument("--plan", required=True, choices=PLANS.keys())
    parser.add_argument("--period", required=True, choices=["monthly", "quarterly", "annual"])
    parser.add_argument("--amount", type=float, required=True)
    args = parser.parse_args()
    result = simulate(args.plan, args.period, args.amount)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
