#!/usr/bin/env python3
"""fee_simulate.py -- CLI tool to simulate fee distribution scenarios.

Usage: python 12_tooling/cli/fee_simulate.py --gross 100.00 --split 70:20:10
"""

import argparse
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))


def simulate(gross: float, split_ratios: list[float]) -> dict:
    """Simulate fee distribution."""
    if abs(sum(split_ratios) - 100.0) > 0.01:
        raise ValueError(f"Split ratios must sum to 100, got {sum(split_ratios)}")
    distributions = [round(gross * r / 100.0, 2) for r in split_ratios]
    remainder = round(gross - sum(distributions), 2)
    if remainder != 0:
        distributions[0] = round(distributions[0] + remainder, 2)
    return {
        "gross_fee": gross,
        "split_ratios": split_ratios,
        "distributions": distributions,
        "invariant_sum_check": sum(distributions) == gross,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate fee distribution")
    parser.add_argument("--gross", type=float, required=True, help="Gross fee amount")
    parser.add_argument("--split", type=str, required=True, help="Colon-separated split ratios (e.g. 70:20:10)")
    args = parser.parse_args()
    ratios = [float(x) for x in args.split.split(":")]
    result = simulate(args.gross, ratios)
    print(json.dumps(result, indent=2))
    return 0 if result["invariant_sum_check"] else 1


if __name__ == "__main__":
    sys.exit(main())
