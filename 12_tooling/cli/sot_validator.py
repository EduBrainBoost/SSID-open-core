#!/usr/bin/env python3
"""
SoT Validator CLI - --verify-all, --scorecard (deprecated: use --breakdown)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = REPO_ROOT / "03_core" / "validators" / "sot" / "sot_validator_core.py"

_INTERFED_ALLOWLIST = (
    "16_codex/",
    "23_compliance/policies/interfederation/",
    "11_test_simulation/",
    "12_tooling/cli/",
)


def check_interfederation_paths(repo_root: Path) -> list[str]:
    """Return tracked paths containing 'interfederation' outside allowlist."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    forbidden = []
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        normalized = entry.replace("\\", "/")
        if "/interfederation/" not in normalized and not normalized.startswith("interfederation/"):
            continue
        if any(normalized.startswith(prefix) for prefix in _INTERFED_ALLOWLIST):
            continue
        forbidden.append(entry)
    return forbidden


def _load_core():
    spec = importlib.util.spec_from_file_location("sot_core", str(CORE_PATH))
    if spec is None or spec.loader is None:
        print("ERROR: Cannot load sot_validator_core")
        raise SystemExit(2)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _generate_breakdown(results: dict) -> dict:
    """Generate score-free breakdown/inventory from validation results."""
    violations = []
    passed = []
    for rule_id in sorted(results.keys()):
        entry = results[rule_id]
        item = {"rule_id": rule_id, "message": entry.get("message", "")}
        if entry.get("status") == "PASS":
            passed.append(item)
        else:
            violations.append(item)

    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "contract_version": "1.0.0",
        "total_rules": len(results),
        "passed_count": len(passed),
        "violation_count": len(violations),
        "status": "FAIL" if violations else "PASS",
        "violations": violations,
        "passed_rules": [r["rule_id"] for r in passed],
    }


def _breakdown_to_md(breakdown: dict) -> str:
    """Render breakdown as markdown (no scores, no percentages)."""
    lines = [
        "# SoT Breakdown (PASS/FAIL inventory)\n",
        f"\nGenerated: {breakdown['generated_at_utc']}\n",
        f"Status: {breakdown['status']}\n",
        f"Rules checked: {breakdown['total_rules']}\n",
        f"Passed: {breakdown['passed_count']}\n",
        f"Violations: {breakdown['violation_count']}\n",
    ]
    if breakdown["violations"]:
        lines.append("\n## Violations\n")
        for v in breakdown["violations"]:
            lines.append(f"- {v['rule_id']}: {v['message']}\n")
    if breakdown["passed_rules"]:
        lines.append("\n## Passed\n")
        for rid in breakdown["passed_rules"]:
            lines.append(f"- {rid}\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="sot_validator.py")
    parser.add_argument(
        "--verify-all", action="store_true",
        help="Run all checks, fail on any violation",
    )
    parser.add_argument(
        "--scorecard", action="store_true",
        help="(deprecated, use --breakdown) Generate breakdown inventory",
    )
    parser.add_argument(
        "--breakdown", action="store_true",
        help="Generate breakdown inventory (PASS/FAIL, counts, lists — no scores)",
    )
    parser.add_argument(
        "--verify-phase5", action="store_true",
        help="Verify Phase-5 SoT Engine Expansion components (SOT_AGENT_037-041)",
    )
    args = parser.parse_args()

    if not CORE_PATH.exists():
        print(f"MISSING: {CORE_PATH}")
        return 2

    mod = _load_core()
    validator = mod.SoTValidatorCore(str(REPO_ROOT))
    results = validator.validate_all()
    ok, failed = validator.evaluate_priorities(results)

    if args.scorecard or args.breakdown:
        breakdown = _generate_breakdown(results)

        out_json = REPO_ROOT / "12_tooling" / "cli" / "scorecard.json"
        out_md = REPO_ROOT / "12_tooling" / "cli" / "scorecard.md"
        out_json.write_text(
            json.dumps(breakdown, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        out_md.write_text(_breakdown_to_md(breakdown), encoding="utf-8")
        print(f"BREAKDOWN: {out_json.as_posix()}, {out_md.as_posix()}")

    if args.verify_phase5:
        phase5_rules = [
            "SOT_AGENT_037", "SOT_AGENT_038", "SOT_AGENT_039",
            "SOT_AGENT_040", "SOT_AGENT_041",
        ]
        phase5_violations = [r for r in failed if r in phase5_rules]
        phase5_passed = [r for r in phase5_rules if r not in phase5_violations]
        print(f"PHASE-5 CHECK: {len(phase5_passed)}/{len(phase5_rules)} rules passed")
        for r in phase5_passed:
            print(f"  PASS: {r}")
        for r in phase5_violations:
            print(f"  FAIL: {r} — {results[r].get('message', '')}")
        if phase5_violations:
            return 2
        print("VERIFIED: All Phase-5 SoT Engine Expansion rules passed")
        return 0

    if args.verify_all:
        forbidden = check_interfederation_paths(REPO_ROOT)
        if forbidden:
            print(f"INTERFEDERATION-SPEC-ONLY: {len(forbidden)} forbidden path(s)")
            for p in forbidden:
                print(f"  {p}")
        if not ok:
            print(f"VIOLATIONS: {', '.join(failed)}")
        if forbidden or not ok:
            return 2
        print("VERIFIED: All SoT rules passed + interfederation SPEC-ONLY clean")
        return 0

    if not (args.scorecard or args.breakdown):
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
