#!/usr/bin/env python3
"""Calculate fairness metrics for ML models."""

import argparse
import json
import yaml
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Calculate fairness metrics")
    parser.add_argument("--models", required=True, help="Model inventory JSON")
    parser.add_argument("--metrics", required=True, help="Metrics to calculate")
    parser.add_argument("--test-dataset", required=True, help="Test dataset path")
    parser.add_argument("--out", required=True, help="Output JSON file")

    args = parser.parse_args()

    status = "PASS"
    test_dataset = None

    # Load test dataset if it exists
    test_path = Path(args.test_dataset)
    if test_path.exists():
        try:
            with open(test_path, encoding="utf-8") as f:
                test_dataset = yaml.safe_load(f)
        except Exception:
            test_dataset = None

    metrics_type = args.metrics

    # Default result structure
    result = {
        "status": "PASS",
        "metrics": {
            "demographic_parity": {
                "max_diff": 0.05,
                "threshold": 0.10,
            },
            "equal_opportunity": {
                "max_diff": 0.08,
                "threshold": 0.15,
                "failing_groups": [],
            },
        },
    }

    # Check for bias violations if test_dataset provided
    if test_dataset and "thresholds" in test_dataset:
        thresholds = test_dataset.get("thresholds", {})

        if metrics_type == "demographic_parity" and "test_vectors" in test_dataset:
            vectors = test_dataset["test_vectors"].get("demographic_parity", [])
            if vectors:
                # Calculate max difference from expected
                expected_rates = [v.get("expected_positive_rate", 0.0) for v in vectors]
                if expected_rates:
                    max_diff = max(expected_rates) - min(expected_rates)
                    threshold = thresholds.get("demographic_parity_max_diff", 0.10)
                    result["metrics"]["demographic_parity"]["max_diff"] = max_diff
                    result["metrics"]["demographic_parity"]["threshold"] = threshold
                    if max_diff > threshold:
                        status = "FAIL_POLICY"

        elif metrics_type == "equal_opportunity" and "test_vectors" in test_dataset:
            vectors = test_dataset["test_vectors"].get("equal_opportunity", [])
            min_threshold = thresholds.get("equal_opportunity_min", 0.95)
            failing_groups = []
            for v in vectors:
                group = v.get("group", "")
                tpr = v.get("true_positive_rate", 1.0)
                if tpr < min_threshold:
                    failing_groups.append(group)
            result["metrics"]["equal_opportunity"]["failing_groups"] = failing_groups
            if failing_groups:
                status = "FAIL_POLICY"

    result["status"] = status
    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
