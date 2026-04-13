"""CLI: check-promotion-gate-policy
Checks compliance for: promotion_gate_policy
Phase 3 stub — A02_A03_COMPLETION
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../23_compliance/validators"))
from validate_promotion_gate_policy import validate_promotion_gate_policy


def main():
    parser = argparse.ArgumentParser(description="Check promotion_gate_policy compliance")
    parser.add_argument("--target", required=True, help="Path to JSON input file or '-' for stdin")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    if args.target == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.target) as f:
            data = json.load(f)

    result = validate_promotion_gate_policy(data)
    status = "PASS" if result else "FAIL"

    if args.output == "json":
        print(json.dumps({"policy": "promotion_gate_policy", "status": status}))
    else:
        print(f"{status}: promotion_gate_policy check for {args.target}")

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
