"""PolicyEnforcer — pre-execution policy hooks for SSID core operations.

Evaluates policy rules before critical distribution/reward actions.
Returns PolicyDecision (ALLOW/DENY) with reason + evidence JSON.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyRuleType(str, Enum):
    MAX_FEE = "max_fee"
    MIN_PARTICIPANTS = "min_participants"
    MAX_GINI = "max_gini"
    MIN_POOL_AMOUNT = "min_pool_amount"
    NON_NEGATIVE_AMOUNT = "non_negative_amount"
    VALID_CURRENCY = "valid_currency"


@dataclass
class PolicyRule:
    rule_type: PolicyRuleType
    threshold: Any  # Decimal, int, float, or set of str depending on rule_type
    description: str = ""


@dataclass
class PolicyDecision:
    action: PolicyAction
    rule_type: PolicyRuleType | None
    reason: str
    context: dict[str, Any]
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def allowed(self) -> bool:
        return self.action == PolicyAction.ALLOW

    def to_evidence(self) -> dict[str, Any]:
        """Serialise decision to evidence dict (JSON-safe)."""
        return {
            "action": self.action.value,
            "rule_type": self.rule_type.value if self.rule_type else None,
            "reason": self.reason,
            "context": {k: str(v) for k, v in self.context.items()},
            "decided_at": self.decided_at.isoformat(),
        }


class PolicyEnforcer:
    """Pre-execution policy enforcement for SSID distribution/reward operations.

    Usage:
        enforcer = PolicyEnforcer()
        decision = enforcer.check_fee_distribution(total_fee, participants)
        if not decision.allowed:
            raise PolicyViolationError(decision.reason)
    """

    DEFAULT_RULES: list[PolicyRule] = [
        PolicyRule(PolicyRuleType.MAX_FEE, Decimal("1_000_000"), "max single fee cap"),
        PolicyRule(PolicyRuleType.MIN_PARTICIPANTS, 1, "must have at least 1 participant"),
        PolicyRule(PolicyRuleType.MAX_GINI, 0.95, "gini must be below 0.95"),
        PolicyRule(PolicyRuleType.MIN_POOL_AMOUNT, Decimal("0"), "pool must be non-negative"),
        PolicyRule(PolicyRuleType.NON_NEGATIVE_AMOUNT, Decimal("0"), "amount non-negative"),
        PolicyRule(PolicyRuleType.VALID_CURRENCY, {"USD", "EUR", "SSID", "BTC", "ETH"}, "must be known currency"),
    ]

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self._rules = {r.rule_type: r for r in (rules or self.DEFAULT_RULES)}
        self._audit_log: list[PolicyDecision] = []

    def _allow(self, context: dict[str, Any]) -> PolicyDecision:
        d = PolicyDecision(PolicyAction.ALLOW, None, "all checks passed", context)
        self._audit_log.append(d)
        return d

    def _deny(self, rule_type: PolicyRuleType, reason: str, context: dict[str, Any]) -> PolicyDecision:
        d = PolicyDecision(PolicyAction.DENY, rule_type, reason, context)
        self._audit_log.append(d)
        return d

    def check_fee_distribution(self, total_fee: Decimal, participants: list[Any]) -> PolicyDecision:
        """Gate FeeDistributionEngine.distribute()."""
        ctx = {"total_fee": total_fee, "participant_count": len(participants)}
        rule = self._rules.get(PolicyRuleType.NON_NEGATIVE_AMOUNT)
        if rule and total_fee < Decimal("0"):
            return self._deny(PolicyRuleType.NON_NEGATIVE_AMOUNT, f"fee {total_fee} is negative", ctx)
        rule = self._rules.get(PolicyRuleType.MAX_FEE)
        if rule and total_fee > rule.threshold:
            return self._deny(PolicyRuleType.MAX_FEE, f"fee {total_fee} exceeds max {rule.threshold}", ctx)
        rule = self._rules.get(PolicyRuleType.MIN_PARTICIPANTS)
        if rule and len(participants) < rule.threshold:
            return self._deny(PolicyRuleType.MIN_PARTICIPANTS, f"need \u2265{rule.threshold} participant(s)", ctx)
        return self._allow(ctx)

    def check_reward_distribution(self, pool_amount: Decimal, participants: list[Any]) -> PolicyDecision:
        """Gate GovernanceRewardEngine.distribute() and RewardHandler.calculate_batch()."""
        ctx = {"pool_amount": pool_amount, "participant_count": len(participants)}
        rule = self._rules.get(PolicyRuleType.MIN_POOL_AMOUNT)
        if rule and pool_amount < rule.threshold:
            return self._deny(PolicyRuleType.MIN_POOL_AMOUNT, f"pool {pool_amount} below minimum", ctx)
        rule = self._rules.get(PolicyRuleType.MIN_PARTICIPANTS)
        if rule and len(participants) < rule.threshold:
            return self._deny(PolicyRuleType.MIN_PARTICIPANTS, f"need \u2265{rule.threshold} participant(s)", ctx)
        return self._allow(ctx)

    def check_fee_proof(self, amount: float, currency: str) -> PolicyDecision:
        """Gate FeeProofEngine.generate_proof()."""
        ctx = {"amount": amount, "currency": currency}
        if amount < 0:
            return self._deny(PolicyRuleType.NON_NEGATIVE_AMOUNT, f"amount {amount} is negative", ctx)
        rule = self._rules.get(PolicyRuleType.VALID_CURRENCY)
        if rule and currency not in rule.threshold:
            return self._deny(PolicyRuleType.VALID_CURRENCY, f"currency '{currency}' not in allowed set", ctx)
        return self._allow(ctx)

    def get_audit_log(self) -> list[PolicyDecision]:
        """Return all decisions recorded so far (in order)."""
        return list(self._audit_log)

    def export_evidence(self) -> list[dict[str, Any]]:
        """Export full audit log as JSON-safe list of evidence dicts."""
        return [d.to_evidence() for d in self._audit_log]


class PolicyViolationError(ValueError):
    """Raised when a policy check returns DENY."""
    def __init__(self, decision: PolicyDecision) -> None:
        super().__init__(f"Policy violation [{decision.rule_type}]: {decision.reason}")
        self.decision = decision
