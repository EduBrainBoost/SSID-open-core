#!/usr/bin/env python3
"""fairness_apply.py -- CLI tool to run fairness checks on scoring vectors.

Usage: python 12_tooling/cli/fairness_apply.py --input scores.json
"""
import argparse
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))


def check_fairness(scores: list[dict]) -> dict:
    """Basic fairness check: no demographic category should deviate >10% from mean."""
    if not scores:
        return {"status": "PASS", "message": "No scores to check"}
    values = [s.get("score", 0) for s in scores]
    mean = sum(values) / len(values)
    deviations = [(s.get("category_hash", "unknown"), abs(s["score"] - mean) / mean * 100 if mean else 0) for s in scores]
    violations = [(cat, dev) for cat, dev in deviations if dev > 10.0]
    return {
        "mean_score": round(mean, 4),
        "total_entries": len(scores),
        "violations": [{"category_hash": c, "deviation_pct": round(d, 2)} for c, d in violations],
        "status": "FAIL" if violations else "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply fairness check")
    parser.add_argument("--input", required=True, help="Path to JSON scores file")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as fh:
        scores = json.load(fh)
    result = check_fairness(scores)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
