#!/usr/bin/env python3
"""AR-10: fee_policy_audit.py
Validates 7-Säulen fee distribution sums to exactly 2.00%.
Checks policy YAML against SoT expected values.
Exits 0 (PASS) or 1 (FAIL_POLICY).
"""

import argparse
import json
import sys
from datetime import UTC
from pathlib import Path

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

EXPECTED_TOTAL = 2.00
EXPECTED_PILLARS = 7


def audit_fee_policy(policy: dict) -> dict:
    pillars = policy.get("pillars", {})
    total_percent = sum(p["percent"] for p in pillars.values())
    tolerance = policy.get("sum_tolerance", 0.001)
    pillar_count = len(pillars)

    checks = {}
    for name, pillar in pillars.items():
        checks[name] = {
            "percent": pillar["percent"],
            "label": pillar.get("label", name),
            "has_destination": bool(pillar.get("destination")),
        }

    sum_correct = abs(total_percent - EXPECTED_TOTAL) <= tolerance
    count_correct = pillar_count == EXPECTED_PILLARS

    status = "PASS" if sum_correct and count_correct else "FAIL_POLICY"
    return {
        "status": status,
        "total_percent": round(total_percent, 6),
        "expected_total": EXPECTED_TOTAL,
        "pillar_count": pillar_count,
        "expected_pillars": EXPECTED_PILLARS,
        "sum_correct": sum_correct,
        "count_correct": count_correct,
        "tolerance": tolerance,
        "pillars": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fee policy 7-Saeulen audit")
    parser.add_argument("--policy", required=True, help="fee_allocation_policy.yaml")
    parser.add_argument("--implementation", help="fee_distribution_engine.py (for reference)")
    parser.add_argument("--sot-doc", help="SoT doc path (for reference)")
    parser.add_argument("--out", required=True, help="Output JSON")
    parser.add_argument("--ems-url", default="", help="EMS base URL for result reporting (optional)")
    parser.add_argument("--run-id", default="", help="Run ID for EMS reporting")
    parser.add_argument("--commit-sha", default="0" * 40, help="Commit SHA for EMS reporting")
    args = parser.parse_args()

    if not HAS_YAML:
        print("ERROR: pyyaml required", file=sys.stderr)
        sys.exit(2)

    policy = yaml.safe_load(Path(args.policy).read_text())
    result = audit_fee_policy(policy)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"Fee policy audit: status={result['status']}, sum={result['total_percent']}% (expected {EXPECTED_TOTAL}%)")

    if args.ems_url:
        try:
            import os as _os
            import sys as _sys

            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "12_tooling"))
            from datetime import datetime as _dt

            from ssid_autorunner.ems_reporter import post_result

            post_result(
                ems_url=args.ems_url,
                ar_id="AR-10",
                run_id=args.run_id or f"CI-AR-10-{_dt.now(UTC).strftime('%Y%m%dT%H%M%S')}",
                result=result,
                commit_sha=args.commit_sha,
            )
        except (ImportError, Exception):
            pass  # ems_reporter optional — never block the gate

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
