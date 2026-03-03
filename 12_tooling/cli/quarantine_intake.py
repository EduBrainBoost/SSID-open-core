#!/usr/bin/env python3
"""
Quarantine Intake — processes quarantine requests with strict reason-code allowlist.
Only security-incident reason codes are permitted. No auto-quarantine from structure/policy.

Canonical quarantine path: 02_audit_logging/quarantine/singleton/quarantine_store/
Evidence hashes:           23_compliance/evidence/malware_quarantine_hashes/

Allowed reason codes: MALWARE, COMPROMISED_BINARY, ACTIVE_EXPLOIT_RISK, DMCA
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUARANTINE_STORE = (
    REPO_ROOT / "02_audit_logging" / "quarantine" / "singleton" / "quarantine_store"
)
HASH_LEDGER = (
    REPO_ROOT / "02_audit_logging" / "quarantine" / "hash_ledger" / "quarantine_chain.json"
)
EVIDENCE_HASHES = (
    REPO_ROOT / "23_compliance" / "evidence" / "malware_quarantine_hashes"
)

ALLOWED_REASON_CODES: set[str] = {
    "MALWARE",
    "COMPROMISED_BINARY",
    "ACTIVE_EXPLOIT_RISK",
    "DMCA",
}


def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_reason_code(code: str) -> bool:
    """Check reason code against allowlist."""
    return code.upper() in ALLOWED_REASON_CODES


def create_intake_entry(
    file_hash: str,
    reason_code: str,
    source_path: str,
    analyst_id: str,
) -> dict:
    """Create a quarantine intake record (hash-only, no payload)."""
    return {
        "schema_version": "1.0.0",
        "intake_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_sha256": file_hash,
        "reason_code": reason_code.upper(),
        "source_path_hash": hashlib.sha256(source_path.encode()).hexdigest(),
        "analyst_id": analyst_id,
        "status": "QUARANTINED",
        "chain_appended": False,
    }


def append_to_chain(entry: dict) -> bool:
    """Append entry to quarantine chain (append-only ledger)."""
    HASH_LEDGER.parent.mkdir(parents=True, exist_ok=True)

    chain: list[dict] = []
    if HASH_LEDGER.exists():
        content = HASH_LEDGER.read_text(encoding="utf-8").strip()
        if content and content != "AUTO-GENERATED PLACEHOLDER (SoT path reference).":
            try:
                data = json.loads(content)
                chain = data.get("entries", [])
            except json.JSONDecodeError:
                chain = []

    # Compute chain hash (each entry hashes the previous)
    prev_hash = chain[-1]["chain_hash"] if chain else "GENESIS"
    chain_input = f"{prev_hash}:{entry['file_sha256']}:{entry['intake_utc']}"
    entry["chain_hash"] = hashlib.sha256(chain_input.encode()).hexdigest()
    entry["chain_appended"] = True
    entry["chain_index"] = len(chain)

    chain.append(entry)

    ledger = {
        "schema_version": "1.0.0",
        "chain_type": "append-only",
        "entry_count": len(chain),
        "entries": chain,
    }

    HASH_LEDGER.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True


def write_evidence_hash(entry: dict) -> None:
    """Write hash-only evidence pointer to compliance evidence path."""
    EVIDENCE_HASHES.mkdir(parents=True, exist_ok=True)
    evidence_file = EVIDENCE_HASHES / f"{entry['file_sha256'][:16]}.json"

    pointer = {
        "file_sha256": entry["file_sha256"],
        "reason_code": entry["reason_code"],
        "intake_utc": entry["intake_utc"],
        "chain_index": entry.get("chain_index", -1),
        "chain_hash": entry.get("chain_hash", ""),
    }

    evidence_file.write_text(
        json.dumps(pointer, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quarantine Intake (security-incident only, hash-only pointers)"
    )
    parser.add_argument(
        "--file", type=str, required=True, help="Path to file to quarantine"
    )
    parser.add_argument(
        "--reason",
        type=str,
        required=True,
        choices=sorted(ALLOWED_REASON_CODES),
        help="Reason code (security-incident only)",
    )
    parser.add_argument(
        "--analyst", type=str, default="system", help="Analyst ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only, do not write to chain or evidence",
    )
    parser.add_argument(
        "--report", type=str, help="Write JSON report to path"
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {args.file}")
        return 2

    if not validate_reason_code(args.reason):
        print(
            f"ERROR: Invalid reason code '{args.reason}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_REASON_CODES))}"
        )
        return 2

    file_hash = sha256_file(file_path)
    entry = create_intake_entry(file_hash, args.reason, args.file, args.analyst)

    if args.dry_run:
        print("DRY-RUN: Intake validation passed")
        print(json.dumps(entry, indent=2))
        return 0

    # Append to chain
    if not append_to_chain(entry):
        print("ERROR: Failed to append to quarantine chain")
        return 1

    # Write evidence hash pointer
    write_evidence_hash(entry)

    print(f"PASS: Quarantined {file_hash[:16]}... (reason={args.reason})")
    print(f"  Chain index: {entry.get('chain_index')}")
    print(f"  Chain hash: {entry.get('chain_hash', '')[:16]}...")

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(entry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report written to: {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
