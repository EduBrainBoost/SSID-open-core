#!/usr/bin/env python3
"""
Quarantine CI Guard — enforces canonical quarantine paths and security-only reason codes.

Scans git diff for quarantine-related changes and verifies:
1. Quarantine writes only to canonical paths
2. Only security reason codes in quarantine_chain.json entries
3. No quarantine data outside the singleton path

PASS: no violations
FAIL: non-canonical write or non-security reason code detected
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CANONICAL_QUARANTINE_PATHS: list[str] = [
    "02_audit_logging/quarantine/singleton/quarantine_store/",
    "02_audit_logging/quarantine/hash_ledger/",
    "02_audit_logging/quarantine/processing/",
    "02_audit_logging/quarantine/quarantine_config_enterprise.yaml",
    "02_audit_logging/quarantine/quarantine_policy.yaml",
    "02_audit_logging/quarantine/retention/",
    "23_compliance/evidence/malware_quarantine_hashes/",
    # Tooling scripts that reference quarantine are canonical CLI tools, not data paths
    "12_tooling/cli/",
]

ALLOWED_REASON_CODES: set[str] = {
    "MALWARE",
    "COMPROMISED_BINARY",
    "ACTIVE_EXPLOIT_RISK",
    "DMCA",
}


def get_changed_files(base: str = "HEAD~1") -> list[str]:
    """Get list of changed files from git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except Exception:
        return []


def is_canonical_quarantine_path(path: str) -> bool:
    """Check if a path is within canonical quarantine paths."""
    return any(path.startswith(canonical) or path == canonical.rstrip("/") for canonical in CANONICAL_QUARANTINE_PATHS)


def check_quarantine_writes(changed_files: list[str]) -> list[str]:
    """Check that quarantine-related writes go to canonical paths only."""
    violations = []
    for f in changed_files:
        if "quarantine" in f.lower() and not is_canonical_quarantine_path(f):
            violations.append(f"NON_CANONICAL_PATH: {f}")
    return violations


def check_reason_codes() -> list[str]:
    """Verify quarantine chain contains only allowed reason codes."""
    chain_path = REPO_ROOT / "02_audit_logging" / "quarantine" / "hash_ledger" / "quarantine_chain.json"
    violations = []

    if not chain_path.exists():
        return []

    content = chain_path.read_text(encoding="utf-8").strip()
    if not content or content == "AUTO-GENERATED PLACEHOLDER (SoT path reference).":
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return ["INVALID_JSON: quarantine_chain.json is not valid JSON"]

    for entry in data.get("entries", []):
        reason = entry.get("reason_code", "")
        if reason not in ALLOWED_REASON_CODES:
            violations.append(f"INVALID_REASON_CODE: '{reason}' at chain_index={entry.get('chain_index')}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine CI Guard (canonical paths + security-only reason codes)")
    parser.add_argument(
        "--base",
        type=str,
        default="HEAD~1",
        help="Git diff base (default: HEAD~1)",
    )
    parser.add_argument("--report", type=str, help="Write JSON report to path")
    args = parser.parse_args()

    print("INFO: [GUARD] Running Quarantine CI Guard...")

    changed = get_changed_files(args.base)
    path_violations = check_quarantine_writes(changed)
    reason_violations = check_reason_codes()

    all_violations = path_violations + reason_violations

    if all_violations:
        for v in all_violations:
            print(f"  FAIL: {v}")
        print(f"\nFAIL: {len(all_violations)} quarantine violation(s)")
    else:
        print("PASS: Quarantine CI Guard — no violations")

    if args.report:
        report = {
            "verdict": "FAIL" if all_violations else "PASS",
            "violations": all_violations,
            "files_checked": len(changed),
        }
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report written to: {args.report}")

    return 1 if all_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
