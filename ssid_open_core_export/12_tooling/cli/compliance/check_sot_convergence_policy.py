"""CLI: check-sot-convergence-policy
Checks compliance for: sot_convergence_policy
Phase 3 stub — A02_A03_COMPLETION
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../23_compliance/validators"))
from validate_sot_convergence_policy import validate_sot_convergence_policy


def main():
    parser = argparse.ArgumentParser(description="Check sot_convergence_policy compliance")
    parser.add_argument("--target", required=True, help="Path to JSON input file or '-' for stdin")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    if args.target == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.target) as f:
            data = json.load(f)

    result = validate_sot_convergence_policy(data)
    status = "PASS" if result else "FAIL"

    if args.output == "json":
        print(json.dumps({"policy": "sot_convergence_policy", "status": status}))
    else:
        print(f"{status}: sot_convergence_policy check for {args.target}")

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
