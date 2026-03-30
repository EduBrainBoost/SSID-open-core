"""ssid-result-contracts — Result contract validation.

Validates that agent result payloads conform to the expected contract:
required fields, correct types, evidence references present.
"""

from typing import Any, Dict, List

from ._evidence import make_evidence, result

SKILL_ID = "ssid-result-contracts"

DEFAULT_REQUIRED_FIELDS = {"status", "evidence_ref"}
VALID_STATUSES = {"PASS", "FAIL", "SKIP", "ERROR", "TIMEOUT"}


def execute(context: Dict) -> Dict:
    """Validate a result payload against its contract.

    context must contain:
        result_payload: dict  — the result to validate
    Optional:
        required_fields: list[str]  — override required fields
        valid_statuses: list[str]   — override valid status values
    """
    payload = context.get("result_payload")
    if payload is None or not isinstance(payload, dict):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "result_payload must be a dict"})
        return result("FAIL", ev, "result_payload required as dict")

    required = set(context.get("required_fields", DEFAULT_REQUIRED_FIELDS))
    statuses = set(context.get("valid_statuses", VALID_STATUSES))

    violations: List[str] = []

    # Check required fields
    for field in required:
        if field not in payload:
            violations.append(f"missing required field: {field}")

    # Check status value
    status_val = payload.get("status", "")
    if status_val and str(status_val).upper() not in statuses:
        violations.append(f"invalid status: {status_val}")

    # Check evidence_ref is non-empty if present
    ev_ref = payload.get("evidence_ref", "")
    if "evidence_ref" in required and not ev_ref:
        violations.append("evidence_ref is empty")

    details = {
        "payload_keys": sorted(payload.keys()),
        "required_fields": sorted(required),
        "violations": violations,
    }

    if violations:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"{len(violations)} contract violation(s)")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "Result contract valid")
