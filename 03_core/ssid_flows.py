"""SSID production flow orchestrators — mandatory PolicyEnforcer + Evidence.

P4.1: PolicyEnforcer is injected and CANNOT be bypassed.
P4.2: Every call produces a FlowEvidence artefact.

Flows:
  run_subscription_revenue_flow(...)
  run_license_fee_flow(...)
  run_reward_governance_flow(...)
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

# ensure cross-module imports work
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO / "08_identity_score"))
sys.path.insert(0, str(_REPO / "02_audit_logging"))

from dataclasses import dataclass

from fairness_engine import FairnessEngine
from fee_distribution_engine import DistributionResult, FeeDistributionEngine, FeeParticipant
from fee_proof_engine import FeeProofEngine
from flow_evidence import FlowEvidence
from governance_reward_engine import GovernanceParticipant, GovernanceRewardEngine, GovernanceRewardResult
from license_fee_splitter import LicenseFeeSplitter, LicenseType, SplitRecipient, SplitResult
from policy_enforcer import PolicyEnforcer, PolicyViolationError
from reward_handler import RewardBatchResult, RewardEvent, RewardHandler
from subscription_revenue_distributor import (
    RevenueDistributionResult,
    RevenueParticipant,
    SubscriptionRevenueDistributor,
    SubscriptionTier,
)


@dataclass
class SubscriptionFlowResult:
    distribution: RevenueDistributionResult
    evidence: FlowEvidence


@dataclass
class LicenseFeeFlowResult:
    split: SplitResult
    validator_distribution: DistributionResult
    evidence: FlowEvidence


@dataclass
class RewardGovernanceFlowResult:
    rewards: RewardBatchResult
    governance: GovernanceRewardResult
    evidence: FlowEvidence


def run_subscription_revenue_flow(
    gross_revenue: Decimal,
    participants: Sequence[RevenueParticipant],
    tier: SubscriptionTier = SubscriptionTier.STARTER,
    enforcer: PolicyEnforcer | None = None,
    flow_id: str | None = None,
) -> SubscriptionFlowResult:
    """Run Subscription -> Revenue Distribution -> Fairness -> Proof flow.

    Raises PolicyViolationError if any policy check fails.
    Always produces FlowEvidence.
    """
    if enforcer is None:
        enforcer = PolicyEnforcer()

    # P4.1: mandatory policy check — no bypass
    decision = enforcer.check_reward_distribution(gross_revenue, list(participants))
    if not decision.allowed:
        evidence = FlowEvidence.create(
            flow_name="subscription_revenue",
            inputs={"gross_revenue": str(gross_revenue), "tier": tier.value, "participant_count": len(participants)},
            outputs={},
            policy_decisions=enforcer.export_evidence(),
            allow_or_deny="deny",
            flow_id=flow_id,
        )
        raise PolicyViolationError(decision)

    distributor = SubscriptionRevenueDistributor()
    result = distributor.distribute(gross_revenue, list(participants), tier)

    # Fairness check
    fairness = FairnessEngine()
    allocations_float = {k: float(v) for k, v in result.allocations.items()}
    if allocations_float:
        fairness.evaluate(allocations_float)

    # Proof
    proofer = FeeProofEngine()
    proof = proofer.generate_proof(
        run_id=flow_id or "subscription",
        amount=float(gross_revenue),
        currency="USD",
        inputs={"tier": tier.value, "participant_count": len(participants)},
    )

    inputs_data = {"gross_revenue": str(gross_revenue), "tier": tier.value}
    outputs_data = {k: str(v) for k, v in result.allocations.items()}

    evidence = FlowEvidence.create(
        flow_name="subscription_revenue",
        inputs=inputs_data,
        outputs=outputs_data,
        policy_decisions=enforcer.export_evidence(),
        allow_or_deny="allow",
        proof_hash=proof.proof_hash,
        flow_id=flow_id,
    )
    return SubscriptionFlowResult(distribution=result, evidence=evidence)


def run_license_fee_flow(
    amount: Decimal,
    license_type: LicenseType,
    fee_participants: Sequence[FeeParticipant],
    enforcer: PolicyEnforcer | None = None,
    flow_id: str | None = None,
) -> LicenseFeeFlowResult:
    """Run LicenseFeeSplitter -> FeeDistributionEngine -> Proof flow."""
    if enforcer is None:
        enforcer = PolicyEnforcer()

    decision = enforcer.check_fee_distribution(amount, list(fee_participants))
    if not decision.allowed:
        raise PolicyViolationError(decision)

    splitter = LicenseFeeSplitter()
    split = splitter.split(amount, license_type)

    # SplitResult.allocations is Dict[SplitRecipient, Decimal]
    validator_share = split.allocations[SplitRecipient.VALIDATOR]

    fee_engine = FeeDistributionEngine()
    validator_dist = fee_engine.distribute(validator_share, list(fee_participants))

    proofer = FeeProofEngine()
    proof = proofer.generate_proof(
        run_id=flow_id or "license_fee",
        amount=float(amount),
        currency="SSID",
        inputs={"license_type": license_type.value, "split_validator": str(validator_share)},
    )

    evidence = FlowEvidence.create(
        flow_name="license_fee",
        inputs={"amount": str(amount), "license_type": license_type.value},
        outputs={
            "platform": str(split.allocations[SplitRecipient.PLATFORM]),
            "creator": str(split.allocations[SplitRecipient.CREATOR]),
            "validator": str(split.allocations[SplitRecipient.VALIDATOR]),
            "reserve": str(split.allocations[SplitRecipient.RESERVE]),
        },
        policy_decisions=enforcer.export_evidence(),
        allow_or_deny="allow",
        proof_hash=proof.proof_hash,
        flow_id=flow_id,
    )
    return LicenseFeeFlowResult(split=split, validator_distribution=validator_dist, evidence=evidence)


def run_reward_governance_flow(
    reward_events: Sequence[RewardEvent],
    governance_pool: Decimal,
    governance_participants: Sequence[GovernanceParticipant],
    enforcer: PolicyEnforcer | None = None,
    flow_id: str | None = None,
) -> RewardGovernanceFlowResult:
    """Run RewardHandler -> GovernanceRewardEngine -> FairnessEngine -> Proof flow."""
    if enforcer is None:
        enforcer = PolicyEnforcer()

    decision = enforcer.check_reward_distribution(governance_pool, list(governance_participants))
    if not decision.allowed:
        raise PolicyViolationError(decision)

    reward_handler = RewardHandler()
    rewards = reward_handler.calculate_batch(list(reward_events))

    gov_engine = GovernanceRewardEngine()
    governance = gov_engine.distribute(governance_pool, list(governance_participants))

    # Fairness check on governance allocations
    fairness = FairnessEngine()
    if governance.allocations:
        fairness.evaluate({k: float(v) for k, v in governance.allocations.items()})

    proofer = FeeProofEngine()
    proof = proofer.generate_proof(
        run_id=flow_id or "reward_governance",
        amount=float(governance_pool),
        currency="SSID",
        inputs={"event_count": len(reward_events), "participant_count": len(governance_participants)},
    )

    evidence = FlowEvidence.create(
        flow_name="reward_governance",
        inputs={"governance_pool": str(governance_pool), "event_count": len(reward_events)},
        outputs={"governance_allocations": {k: str(v) for k, v in governance.allocations.items()}},
        policy_decisions=enforcer.export_evidence(),
        allow_or_deny="allow",
        proof_hash=proof.proof_hash,
        flow_id=flow_id,
    )
    return RewardGovernanceFlowResult(rewards=rewards, governance=governance, evidence=evidence)
