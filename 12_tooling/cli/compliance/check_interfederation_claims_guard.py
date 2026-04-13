"""CLI: check-interfederation-claims-guard
Checks compliance for: interfederation_claims_guard
Phase 3 stub — A02_A03_COMPLETION
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../23_compliance/validators"))
from validate_interfederation_claims_guard import validate_interfederation_claims_guard


def main():
    parser = argparse.ArgumentParser(description="Check interfederation_claims_guard compliance")
    parser.add_argument("--target", required=True, help="Path to JSON input file or '-' for stdin")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    if args.target == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.target) as f:
            data = json.load(f)

    result = validate_interfederation_claims_guard(data)
    status = "PASS" if result else "FAIL"

    if args.output == "json":
        print(json.dumps({"policy": "interfederation_claims_guard", "status": status}))
    else:
        print(f"{status}: interfederation_claims_guard check for {args.target}")

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
