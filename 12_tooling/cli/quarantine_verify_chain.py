#!/usr/bin/env python3
"""
Quarantine Chain Verifier — validates append-only integrity of quarantine_chain.json.
Recomputes chain hashes and verifies no entries were modified or removed.

PASS: chain is valid (or genesis/empty)
FAIL: chain integrity violation detected
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HASH_LEDGER = REPO_ROOT / "02_audit_logging" / "quarantine" / "hash_ledger" / "quarantine_chain.json"


def verify_chain(ledger_path: Path) -> tuple[bool, list[str]]:
    """Verify quarantine chain integrity. Returns (ok, findings)."""
    findings: list[str] = []

    if not ledger_path.exists():
        return True, ["INFO: quarantine_chain.json does not exist (genesis state)"]

    content = ledger_path.read_text(encoding="utf-8").strip()

    # Handle placeholder files from TS001 scaffold
    if content == "AUTO-GENERATED PLACEHOLDER (SoT path reference).":
        return True, ["INFO: quarantine_chain.json is genesis placeholder"]

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"FAIL: quarantine_chain.json is not valid JSON: {e}"]

    if not isinstance(data, dict):
        return False, ["FAIL: quarantine_chain.json root is not an object"]

    entries = data.get("entries", [])
    if not entries:
        return True, ["INFO: quarantine chain is empty (no entries)"]

    # Verify chain hash integrity
    for i, entry in enumerate(entries):
        expected_index = i
        if entry.get("chain_index") != expected_index:
            findings.append(f"FAIL: Entry {i} has chain_index={entry.get('chain_index')}, expected {expected_index}")
            continue

        prev_hash = entries[i - 1]["chain_hash"] if i > 0 else "GENESIS"
        chain_input = f"{prev_hash}:{entry['file_sha256']}:{entry['intake_utc']}"
        computed_hash = hashlib.sha256(chain_input.encode()).hexdigest()

        if entry.get("chain_hash") != computed_hash:
            findings.append(
                f"FAIL: Entry {i} chain_hash mismatch: "
                f"stored={entry.get('chain_hash', '')[:16]}... "
                f"computed={computed_hash[:16]}..."
            )

    # Check entry count consistency
    declared = data.get("entry_count", -1)
    if declared != len(entries):
        findings.append(f"FAIL: Declared entry_count={declared} but found {len(entries)} entries")

    fail_count = sum(1 for f in findings if f.startswith("FAIL"))
    if fail_count > 0:
        return False, findings

    findings.append(f"PASS: Chain verified ({len(entries)} entries, all hashes valid)")
    return True, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine Chain Verifier (append-only integrity check)")
    parser.add_argument(
        "--ledger",
        type=str,
        default=str(HASH_LEDGER),
        help="Path to quarantine_chain.json",
    )
    parser.add_argument("--report", type=str, help="Write JSON report to path")
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    ok, findings = verify_chain(ledger_path)

    for f in findings:
        print(f)

    verdict = "PASS" if ok else "FAIL"
    print(f"\nVerdict: {verdict}")

    if args.report:
        report = {
            "verdict": verdict,
            "ledger_path": str(ledger_path),
            "findings": findings,
        }
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report written to: {args.report}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
