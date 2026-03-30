"""OPA policy hook for Admin API. Evaluates Rego policies locally."""

from __future__ import annotations

import json
import os
from typing import Any


def evaluate_policy(user_role: str, resource: str, action: str) -> dict[str, Any]:
    """Evaluate admin RBAC policy. Returns {"allowed": bool, "reason": str}.
    MVP: role-based check. Production: OPA/WASM evaluation."""
    role_permissions = {
        "superadmin": {"*"},
        "auditor": {"read", "audit", "export"},
        "operator": {"read", "write", "execute"},
        "viewer": {"read"},
    }

    allowed_actions = role_permissions.get(user_role, set())
    if "*" in allowed_actions or action in allowed_actions:
        return {"allowed": True, "reason": "role_permits"}
    return {"allowed": False, "reason": f"role '{user_role}' cannot '{action}' on '{resource}'"}
