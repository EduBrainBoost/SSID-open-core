"""ssid-loop-recovery — Loop detection and recovery.

Detects when an agent is stuck in a retry loop by tracking
repeated identical operations and triggering recovery.
"""

import hashlib

from ._evidence import make_evidence, result

SKILL_ID = "ssid-loop-recovery"


def _hash_action(action: dict) -> str:
    """Create a fingerprint for an action to detect repetition."""
    key_parts = [
        str(action.get("operation", "")),
        str(action.get("target", "")),
        str(action.get("skill_id", "")),
    ]
    return hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:16]


def execute(context: dict) -> dict:
    """Detect loops in action history.

    context must contain:
        action_history: list[dict]  — ordered list of recent actions
            Each action: {operation, target, skill_id, timestamp}
    Optional:
        max_repeats: int  — threshold for loop detection (default 3)
    """
    history = context.get("action_history")
    if not isinstance(history, list):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "action_history must be a list"})
        return result("FAIL", ev, "action_history required as list")

    max_repeats = context.get("max_repeats", 3)

    # Count consecutive identical action hashes
    fingerprints = [_hash_action(a) for a in history]
    loops_detected: list[dict] = []

    if len(fingerprints) >= max_repeats:
        # Sliding window for consecutive repeats
        i = 0
        while i < len(fingerprints):
            count = 1
            while i + count < len(fingerprints) and fingerprints[i + count] == fingerprints[i]:
                count += 1
            if count >= max_repeats:
                loops_detected.append(
                    {
                        "fingerprint": fingerprints[i],
                        "consecutive_count": count,
                        "start_index": i,
                    }
                )
            i += count

    details = {
        "total_actions": len(history),
        "max_repeats_threshold": max_repeats,
        "loops_detected": loops_detected,
    }

    if loops_detected:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"Loop detected: {len(loops_detected)} pattern(s) repeating >={max_repeats}x")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "No loops detected in action history")
