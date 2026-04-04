"""ssid-run-lifecycle — Run status management.

Manages and validates the lifecycle of agent runs:
PENDING -> RUNNING -> COMPLETED | FAILED | TIMEOUT
"""

from ._evidence import make_evidence, result

SKILL_ID = "ssid-run-lifecycle"

VALID_STATES = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "TIMEOUT"}

VALID_TRANSITIONS = {
    "PENDING": {"RUNNING", "FAILED"},
    "RUNNING": {"COMPLETED", "FAILED", "TIMEOUT"},
    "COMPLETED": set(),
    "FAILED": {"PENDING"},  # allow retry
    "TIMEOUT": {"PENDING"},  # allow retry
}


def execute(context: dict) -> dict:
    """Validate or perform a run state transition.

    context must contain:
        current_state: str
        requested_state: str
        run_id: str
    """
    current = context.get("current_state", "").upper()
    requested = context.get("requested_state", "").upper()
    run_id = context.get("run_id", "unknown")

    if current not in VALID_STATES:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": f"invalid current_state: {current}"})
        return result("FAIL", ev, f"Unknown current state: {current}")

    if requested not in VALID_STATES:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": f"invalid requested_state: {requested}"})
        return result("FAIL", ev, f"Unknown requested state: {requested}")

    allowed = VALID_TRANSITIONS.get(current, set())

    details = {
        "run_id": run_id,
        "current_state": current,
        "requested_state": requested,
        "allowed_transitions": sorted(allowed),
        "transition_valid": requested in allowed,
    }

    if requested not in allowed:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"Transition {current}->{requested} not allowed")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, f"Transition {current}->{requested} valid for run {run_id}")
