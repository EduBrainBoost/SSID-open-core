#!/usr/bin/env python3
"""AR-10: dao_params_check.py
Validates DAO governance parameters are within policy-defined ranges.
Exits 0 (PASS) or 1 (FAIL_QA).
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


def check_params(policy: dict, actual_params: dict | None = None) -> dict:
    """
    Validate DAO params against policy ranges.
    If actual_params is None, validates the policy defaults are within range.
    """
    dao_params_spec = policy.get("dao_params", {})
    results = {}
    failures = []

    # Use actual params if provided, otherwise validate defaults
    params_to_check = actual_params or {k: v.get("default") for k, v in dao_params_spec.items()}

    for param_name, spec in dao_params_spec.items():
        value = params_to_check.get(param_name)
        if value is None:
            results[param_name] = {
                "status": "MISSING",
                "value": None,
                "range": [spec.get("min"), spec.get("max")],
            }
            failures.append(param_name)
            continue

        min_val = spec.get("min")
        max_val = spec.get("max")
        in_range = (min_val is None or value >= min_val) and (max_val is None or value <= max_val)

        if not in_range:
            failures.append(param_name)

        results[param_name] = {
            "status": "PASS" if in_range else "FAIL_QA",
            "value": value,
            "range": [min_val, max_val],
            "default": spec.get("default"),
        }

    status = "PASS" if not failures else "FAIL_QA"
    return {
        "status": status,
        "failures": failures,
        "params": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DAO parameter range check")
    parser.add_argument("--policy", required=True, help="subscription_revenue_policy.yaml")
    parser.add_argument("--actual-params", help="JSON of actual DAO params to validate")
    parser.add_argument("--out", required=True, help="Output JSON")
    args = parser.parse_args()

    if not HAS_YAML:
        print("ERROR: pyyaml required", file=sys.stderr)
        sys.exit(2)

    policy = yaml.safe_load(Path(args.policy).read_text())
    actual = None
    if args.actual_params:
        actual = json.loads(Path(args.actual_params).read_text())

    result = check_params(policy, actual)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"DAO params check: status={result['status']}, failures={result['failures']}")

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
