"""ssid-evidence-discipline — Evidence completeness check.

Validates that evidence records contain all required fields
and SHA-256 hashes are well-formed.
"""

import re
from typing import Any, Dict, List

from ._evidence import make_evidence, result

SKILL_ID = "ssid-evidence-discipline"

REQUIRED_FIELDS = {"timestamp", "agent_id", "operation", "file_affected", "sha256_after"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _validate_record(record: Dict[str, Any]) -> List[str]:
    """Return list of violation messages for a single evidence record."""
    violations = []
    for field in REQUIRED_FIELDS:
        if field not in record or record[field] is None:
            violations.append(f"missing field: {field}")

    sha_after = record.get("sha256_after", "")
    if sha_after and not SHA256_RE.match(str(sha_after)):
        violations.append(f"malformed sha256_after: {sha_after}")

    sha_before = record.get("sha256_before")
    if sha_before is not None and sha_before != "null" and not SHA256_RE.match(str(sha_before)):
        violations.append(f"malformed sha256_before: {sha_before}")

    return violations


def execute(context: Dict) -> Dict:
    """Validate evidence records for completeness.

    context must contain:
        evidence_records: list[dict]  — list of evidence entries to check
    """
    records = context.get("evidence_records")
    if records is None:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "evidence_records not provided"})
        return result("FAIL", ev, "evidence_records required in context")

    if not isinstance(records, list):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "evidence_records must be a list"})
        return result("FAIL", ev, "evidence_records must be a list")

    total = len(records)
    all_violations: List[Dict] = []

    for idx, rec in enumerate(records):
        v = _validate_record(rec)
        if v:
            all_violations.append({"index": idx, "violations": v})

    details = {
        "total_records": total,
        "valid_count": total - len(all_violations),
        "invalid_count": len(all_violations),
        "violations": all_violations[:20],  # cap detail output
    }

    if all_violations:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"{len(all_violations)}/{total} evidence records invalid")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, f"All {total} evidence records valid")
