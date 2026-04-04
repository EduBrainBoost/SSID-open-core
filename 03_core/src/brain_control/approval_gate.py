"""Approval gate: fail-closed enforcement for critical actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateDecision(Enum):
    APPROVED = "approved"
    DENIED = "denied"
    REQUIRES_REVIEW = "requires_review"


CRITICAL_ACTIONS = {"write", "delete", "deploy", "merge", "push", "modify_policy", "modify_registry"}


@dataclass
class GateResult:
    action: str
    decision: GateDecision
    reason: str
    requires_human: bool = False


class ApprovalGate:
    def __init__(self, auto_approve: list[str] | None = None):
        self.auto_approve = set(auto_approve or ["read", "search", "query", "list"])

    def check(self, action: str, scope: str = "", role: str = "user") -> GateResult:
        if action in self.auto_approve:
            return GateResult(action=action, decision=GateDecision.APPROVED, reason="auto-approved read action")
        if action in CRITICAL_ACTIONS:
            if role == "admin":
                return GateResult(action=action, decision=GateDecision.APPROVED, reason="admin override")
            return GateResult(
                action=action,
                decision=GateDecision.DENIED,
                reason=f"critical action '{action}' requires admin role",
                requires_human=True,
            )
        return GateResult(
            action=action, decision=GateDecision.REQUIRES_REVIEW, reason="unknown action type", requires_human=True
        )
