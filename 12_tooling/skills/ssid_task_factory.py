"""ssid-task-factory — Task creation from templates.

Creates validated task assignments from templates,
ensuring all required fields and scope constraints.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ._evidence import make_evidence, result

SKILL_ID = "ssid-task-factory"

REQUIRED_TASK_FIELDS = {"task_id", "skill_id", "scope", "target", "agent_group"}

TASK_TEMPLATE = {
    "task_id": "",
    "skill_id": "",
    "scope": "",
    "target": "",
    "agent_group": "",
    "priority": "normal",
    "created_at": "",
    "timeout_seconds": 300,
}


def _generate_task_id(skill_id: str, target: str) -> str:
    """Generate a deterministic task ID from skill + target."""
    raw = f"{skill_id}:{target}:{datetime.now(timezone.utc).isoformat()}"
    return f"task-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def execute(context: Dict) -> Dict:
    """Create a task from template, or validate an existing task.

    For task creation, context must contain:
        mode: "create"
        skill_id: str
        scope: str
        target: str
        agent_group: str
    Optional:
        priority: str  — "low", "normal", "high" (default "normal")
        timeout_seconds: int  — default 300

    For task validation, context must contain:
        mode: "validate"
        task_payload: dict  — the task to validate
    """
    mode = context.get("mode", "validate")

    if mode == "create":
        skill_id = context.get("skill_id", "")
        scope = context.get("scope", "")
        target = context.get("target", "")
        agent_group = context.get("agent_group", "")

        missing = []
        if not skill_id:
            missing.append("skill_id")
        if not scope:
            missing.append("scope")
        if not target:
            missing.append("target")
        if not agent_group:
            missing.append("agent_group")

        if missing:
            ev = make_evidence(SKILL_ID, "FAIL", {"missing": missing})
            return result("FAIL", ev, f"Cannot create task: missing {missing}")

        task = dict(TASK_TEMPLATE)
        task["task_id"] = _generate_task_id(skill_id, target)
        task["skill_id"] = skill_id
        task["scope"] = scope
        task["target"] = target
        task["agent_group"] = agent_group
        task["priority"] = context.get("priority", "normal")
        task["timeout_seconds"] = context.get("timeout_seconds", 300)
        task["created_at"] = datetime.now(timezone.utc).isoformat()

        details = {"task": task}
        ev = make_evidence(SKILL_ID, "PASS", details)
        r = result("PASS", ev, f"Task {task['task_id']} created")
        r["task"] = task
        return r

    elif mode == "validate":
        payload = context.get("task_payload", {})
        if not isinstance(payload, dict):
            ev = make_evidence(SKILL_ID, "FAIL", {"reason": "task_payload must be dict"})
            return result("FAIL", ev, "task_payload must be a dict")

        violations: List[str] = []
        for field in REQUIRED_TASK_FIELDS:
            if field not in payload or not payload[field]:
                violations.append(f"missing: {field}")

        details = {"violations": violations, "payload_keys": sorted(payload.keys())}

        if violations:
            ev = make_evidence(SKILL_ID, "FAIL", details)
            return result("FAIL", ev, f"{len(violations)} task contract violation(s)")

        ev = make_evidence(SKILL_ID, "PASS", details)
        return result("PASS", ev, "Task payload valid")

    else:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": f"unknown mode: {mode}"})
        return result("FAIL", ev, f"Unknown mode: {mode}. Use 'create' or 'validate'")
