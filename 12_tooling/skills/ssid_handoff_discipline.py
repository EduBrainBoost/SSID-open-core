"""ssid-handoff-discipline — Handoff validation.

Ensures agent handoffs include all required context:
run state, evidence chain, lock transfer, and scope declaration.
"""

from typing import Dict, List

from ._evidence import make_evidence, result

SKILL_ID = "ssid-handoff-discipline"

REQUIRED_HANDOFF_FIELDS = {
    "source_agent_id",
    "target_agent_id",
    "run_id",
    "run_state",
    "evidence_chain_ref",
    "scope",
}


def execute(context: Dict) -> Dict:
    """Validate a handoff payload.

    context must contain:
        handoff_payload: dict  — the handoff record to validate
    """
    payload = context.get("handoff_payload")
    if payload is None or not isinstance(payload, dict):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "handoff_payload required as dict"})
        return result("FAIL", ev, "handoff_payload required")

    violations: List[str] = []

    for field in REQUIRED_HANDOFF_FIELDS:
        if field not in payload or not payload[field]:
            violations.append(f"missing or empty: {field}")

    # Source and target must differ
    src = payload.get("source_agent_id", "")
    tgt = payload.get("target_agent_id", "")
    if src and tgt and src == tgt:
        violations.append("source_agent_id equals target_agent_id (self-handoff)")

    # Run state must be valid for handoff
    state = str(payload.get("run_state", "")).upper()
    if state and state not in {"COMPLETED", "FAILED", "TIMEOUT", "PENDING"}:
        violations.append(f"invalid run_state for handoff: {state}")

    details = {
        "payload_keys": sorted(payload.keys()),
        "violations": violations,
        "source": src,
        "target": tgt,
    }

    if violations:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"{len(violations)} handoff violation(s)")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "Handoff payload valid")
