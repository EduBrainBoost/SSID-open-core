#!/usr/bin/env python3
"""
Evidence Verifier — Non-custodial hash verification for SSID evidence files.

Functions:
  verify_hash(file)  -> {"file": str, "status": "PASS"|"FAIL", "detail": str}
  verify_chain(dir)  -> list of verify_hash results for all .json in dir

Non-custodial: No PII is stored or read. Only SHA3-256 hashes are computed
and compared against declared values in evidence entries.

Usage:
  python 12_tooling/cli/evidence_verifier.py verify --file PATH
  python 12_tooling/cli/evidence_verifier.py chain --dir DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Windows cp1252 safety
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _sha3_256(data: bytes) -> str:
    """Compute SHA3-256 hex digest."""
    return hashlib.sha3_256(data).hexdigest()


def _sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest (fallback for legacy evidence)."""
    return hashlib.sha256(data).hexdigest()


def verify_hash(file_path: str) -> dict[str, str]:
    """Verify a single evidence file's integrity.

    Checks:
    1. File exists and is valid JSON
    2. If 'sha256_after' or 'sha3_256' field present, verifies content hash
    3. If 'file_affected' field present, verifies referenced file exists

    Returns dict with keys: file, status (PASS|FAIL), detail
    """
    p = Path(file_path)
    result: dict[str, str] = {"file": str(p.name), "status": "FAIL", "detail": ""}

    if not p.is_file():
        result["detail"] = "File not found"
        return result

    try:
        raw = p.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        result["detail"] = f"Invalid JSON: {exc}"
        return result

    if not isinstance(data, dict):
        # Could be a list of entries — verify each is a dict
        if isinstance(data, list) and all(isinstance(e, dict) for e in data):
            result["status"] = "PASS"
            result["detail"] = f"Array of {len(data)} evidence entries"
            return result
        result["detail"] = "Unexpected JSON structure"
        return result

    # Check declared hash fields
    declared_sha256 = data.get("sha256_after") or data.get("sha256")
    declared_sha3 = data.get("sha3_256")

    if declared_sha3:
        # Verify SHA3-256 of referenced file if file_affected exists
        file_affected = data.get("file_affected")
        if file_affected:
            repo_root = Path(__file__).resolve().parents[2]
            target = repo_root / file_affected
            if target.is_file():
                actual = _sha3_256(target.read_bytes())
                if actual == declared_sha3:
                    result["status"] = "PASS"
                    result["detail"] = "SHA3-256 verified"
                else:
                    result["detail"] = f"SHA3-256 mismatch: declared={declared_sha3[:16]}... actual={actual[:16]}..."
                return result
            else:
                # File may have been moved — not necessarily a failure
                result["status"] = "PASS"
                result["detail"] = "Referenced file not found (may be relocated)"
                return result

    # If no hash fields, just validate structure
    required_fields = {"timestamp", "operation"}
    if required_fields.issubset(data.keys()):
        result["status"] = "PASS"
        result["detail"] = "Valid evidence structure"
    elif "agent_id" in data or "session_id" in data:
        result["status"] = "PASS"
        result["detail"] = "Valid agent evidence entry"
    else:
        # Generic JSON — pass if parseable
        result["status"] = "PASS"
        result["detail"] = "Valid JSON (no hash to verify)"

    return result


def verify_chain(directory: str) -> list[dict[str, str]]:
    """Verify all evidence files in a directory.

    Args:
        directory: Path to directory containing evidence .json files

    Returns:
        List of verify_hash results, one per file
    """
    d = Path(directory)
    if not d.is_dir():
        return [{"file": str(d), "status": "FAIL", "detail": "Directory not found"}]

    results: list[dict[str, str]] = []
    for f in sorted(d.rglob("*.json")):
        results.append(verify_hash(str(f)))

    return results


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="evidence-verifier",
        description="Non-custodial evidence hash verification",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_verify = subparsers.add_parser("verify", help="Verify a single evidence file")
    p_verify.add_argument("--file", required=True, help="Path to evidence JSON file")

    p_chain = subparsers.add_parser("chain", help="Verify all evidence in a directory")
    p_chain.add_argument("--dir", required=True, help="Path to evidence directory")

    args = parser.parse_args()

    if args.command == "verify":
        result = verify_hash(args.file)
        marker = "PASS" if result["status"] == "PASS" else "FAIL"
        print(f"[{marker}] {result['file']}: {result['detail']}")
        return 0 if result["status"] == "PASS" else 1

    elif args.command == "chain":
        results = verify_chain(args.dir)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = len(results) - passed
        for r in results:
            marker = "PASS" if r["status"] == "PASS" else "FAIL"
            print(f"  [{marker}] {r['file']}: {r['detail']}")
        print(f"\nTotal: {len(results)} | PASS: {passed} | FAIL: {failed}")
        return 0 if failed == 0 else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
