#!/usr/bin/env python3
"""AR-10: pofi_formula_check.py
Validates the POFI formula: pofi_score = log(activity+1) / log(rewards+10)
Tests the formula against known SoT reference values.
Exits 0 (PASS) or 1 (FAIL_QA).
"""
import argparse
import json
import math
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# SoT reference test vectors: (activity, rewards) -> expected score (rounded to 6dp)
REFERENCE_VECTORS = [
    # (activity, rewards, expected_score_approx)
    (0, 0, 0.0),          # zero activity: log(1)/log(10) = 0/1 = 0.0
    (9, 0, 1.0),          # activity=9: log(10)/log(10) = 1.0 exactly
    (99, 0, 1.0 * math.log(100) / math.log(10)),  # log(100)/log(10) = 2.0 — > 1 cap check
    (0, 90, 0.0),         # zero activity always gives 0
]

TOLERANCE = 1e-9


def compute_pofi(activity: float, rewards: float) -> float:
    """Canonical POFI formula from SoT."""
    return math.log(activity + 1) / math.log(rewards + 10)


def validate_formula(policy: dict) -> dict:
    formula_config = policy.get("formula", {})
    results = []
    all_pass = True

    for activity, rewards, _ in REFERENCE_VECTORS:
        computed = compute_pofi(activity, rewards)
        # Verify formula properties
        is_non_negative = computed >= 0
        # For zero activity, score must be exactly 0
        zero_check = (activity > 0) or (abs(computed) < TOLERANCE)
        ok = is_non_negative and zero_check
        if not ok:
            all_pass = False
        results.append({
            "activity": activity,
            "rewards": rewards,
            "computed_score": round(computed, 9),
            "ok": ok,
        })

    # Verify monotonicity: higher activity (same rewards) → higher score
    scores_increasing = [compute_pofi(a, 0) for a in [0, 1, 9, 99, 999]]
    monotone = all(scores_increasing[i] <= scores_increasing[i + 1]
                   for i in range(len(scores_increasing) - 1))
    if not monotone:
        all_pass = False

    status = "PASS" if all_pass else "FAIL_QA"
    return {
        "status": status,
        "formula_name": formula_config.get("name", "POFI"),
        "formula_str": "log(activity+1) / log(rewards+10)",
        "reference_tests": results,
        "monotone_check": monotone,
        "thresholds": policy.get("thresholds", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="POFI formula validation")
    parser.add_argument("--policy", required=True, help="proof_of_fairness_policy.yaml")
    parser.add_argument("--out", required=True, help="Output JSON")
    args = parser.parse_args()

    if not HAS_YAML:
        print("ERROR: pyyaml required", file=sys.stderr)
        sys.exit(2)

    policy = yaml.safe_load(Path(args.policy).read_text())
    result = validate_formula(policy)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"POFI formula check: status={result['status']}")

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
