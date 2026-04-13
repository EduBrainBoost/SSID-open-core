"""ssid-branch-worktree-lock — Branch/worktree isolation check.

Verifies that the current git worktree has a proper lock file
and no foreign locks are active.
"""

import os

from ._evidence import make_evidence, result

SKILL_ID = "ssid-branch-worktree-lock"


def execute(context: dict) -> dict:
    """Check branch/worktree isolation via lock files.

    context must contain:
        workspace_root: str
        agent_id: str  — the current agent's identifier
    """
    workspace_root = context.get("workspace_root", "")
    agent_id = context.get("agent_id", "")

    if not workspace_root or not agent_id:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "workspace_root and agent_id required"})
        return result("FAIL", ev, "workspace_root and agent_id are required")

    lock_dir = os.path.join(workspace_root, ".ssid-system", "locks")

    if not os.path.isdir(lock_dir):
        details = {"lock_dir": lock_dir, "exists": False, "agent_id": agent_id}
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, "Lock directory does not exist")

    own_lock = os.path.join(lock_dir, f"{agent_id}.lock")
    has_own_lock = os.path.isfile(own_lock)

    # Scan for foreign locks
    foreign_locks = []
    for f in os.listdir(lock_dir):
        if f.endswith(".lock") and f != f"{agent_id}.lock":
            foreign_locks.append(f)

    details = {
        "agent_id": agent_id,
        "own_lock_exists": has_own_lock,
        "foreign_locks": foreign_locks,
        "lock_dir": lock_dir,
    }

    if not has_own_lock:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"No lock file for agent {agent_id}")

    if foreign_locks:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"{len(foreign_locks)} foreign lock(s) detected")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "Worktree isolation confirmed")
