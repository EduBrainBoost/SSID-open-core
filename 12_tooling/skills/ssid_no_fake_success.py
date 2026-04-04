"""ssid-no-fake-success — Anti-fake-success gate.

Detects result payloads that claim PASS but lack real evidence,
have empty verification, or contain known fake-success patterns.
"""

import re

from ._evidence import make_evidence, result

SKILL_ID = "ssid-no-fake-success"

# Patterns that indicate fake or shallow success claims
FAKE_PATTERNS = [
    re.compile(r"(?i)assumed?\s+pass"),
    re.compile(r"(?i)skip(ped)?\s+verif"),
    re.compile(r"(?i)no\s+test(s)?\s+ran"),
    re.compile(r"(?i)placeholder"),
    re.compile(r"(?i)todo.*pass"),
    re.compile(r"(?i)stub(bed)?"),
]


def execute(context: dict) -> dict:
    """Detect fake success in a result payload.

    context must contain:
        result_payload: dict — must have status, evidence_ref, and optionally message
    """
    payload = context.get("result_payload")
    if payload is None or not isinstance(payload, dict):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "result_payload required as dict"})
        return result("FAIL", ev, "result_payload required")

    status = str(payload.get("status", "")).upper()
    evidence_ref = payload.get("evidence_ref", "")
    message = str(payload.get("message", ""))

    suspicions: list[str] = []

    # PASS without evidence is suspicious
    if status == "PASS" and not evidence_ref:
        suspicions.append("PASS claimed but no evidence_ref")

    # Check message for fake patterns
    for pattern in FAKE_PATTERNS:
        if pattern.search(message):
            suspicions.append(f"fake pattern detected: {pattern.pattern}")

    # PASS with zero details
    details_field = payload.get("details", payload.get("evidence", {}))
    if status == "PASS" and isinstance(details_field, dict) and len(details_field) == 0:
        suspicions.append("PASS with empty details/evidence")

    details = {
        "status": status,
        "has_evidence_ref": bool(evidence_ref),
        "message_length": len(message),
        "suspicions": suspicions,
    }

    if suspicions:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"Fake success detected: {len(suspicions)} issue(s)")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "No fake success indicators found")
