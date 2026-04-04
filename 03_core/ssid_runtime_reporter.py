"""ssid_runtime_reporter.py — EMS-consumable SSID runtime status export.

P5.1: Provides read-only runtime status for all 3 SSID core flows.
P5.2: EMS can consume this via file-read or direct Python import.

Usage:
    from ssid_runtime_reporter import SsidRuntimeReporter
    reporter = SsidRuntimeReporter()
    report = reporter.generate_report()
    reporter.export_to_file("ssid_runtime_status.json")
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO / "08_identity_score"))
sys.path.insert(0, str(_REPO / "02_audit_logging"))

from ems_contract import (
    SCHEMA_VERSION,
    FlowStatusPayload,
    ModuleHealthPayload,
    get_module_health_payloads,
)
from fee_distribution_engine import FeeParticipant, ParticipantRole
from governance_reward_engine import (
    GovernanceActivity,
    GovernanceActivityType,
    GovernanceParticipant,
)
from license_fee_splitter import LicenseType
from policy_enforcer import PolicyViolationError
from reward_handler import RewardAction, RewardEvent
from ssid_flows import (
    run_license_fee_flow,
    run_reward_governance_flow,
    run_subscription_revenue_flow,
)
from subscription_revenue_distributor import RevenueParticipant, SubscriptionTier


@dataclass
class SsidRuntimeReport:
    """Full runtime status snapshot of SSID core flows."""

    schema_version: str
    generated_at: str
    module_health: list[dict[str, str]]
    flow_statuses: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "module_health": self.module_health,
            "flow_statuses": self.flow_statuses,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class SsidRuntimeReporter:
    """Generates EMS-consumable runtime status snapshots for all SSID core flows."""

    # Sample fixture data for health checks (deterministic, no randomness)
    _SAMPLE_REVENUE_PARTICIPANTS = [
        RevenueParticipant(participant_id="provider_a", service_units=100),
        RevenueParticipant(participant_id="provider_b", service_units=80),
        RevenueParticipant(participant_id="provider_c", service_units=60),
    ]
    _SAMPLE_FEE_PARTICIPANTS = [
        FeeParticipant(participant_id="validator_1", role=ParticipantRole.VALIDATOR, contribution_score=0.9),
        FeeParticipant(participant_id="provider_1", role=ParticipantRole.PROVIDER, contribution_score=0.7),
    ]
    _SAMPLE_GOVERNANCE_PARTICIPANTS = [
        GovernanceParticipant(
            participant_id="gov_a",
            activities=[GovernanceActivity(activity_type=GovernanceActivityType.VOTE, weight=1.0)],
        ),
        GovernanceParticipant(
            participant_id="gov_b",
            activities=[GovernanceActivity(activity_type=GovernanceActivityType.PROPOSAL, weight=1.0)],
        ),
    ]
    _SAMPLE_REWARD_EVENTS = [
        RewardEvent(
            event_id="evt_probe_1",
            participant_id="gov_a",
            action=RewardAction.GOVERNANCE_VOTE,
            quantity=3,
            quality_score=0.9,
        ),
        RewardEvent(
            event_id="evt_probe_2",
            participant_id="gov_b",
            action=RewardAction.GOVERNANCE_VOTE,
            quantity=2,
            quality_score=0.8,
        ),
    ]

    def _probe_subscription_flow(self) -> dict[str, Any]:
        """Probe subscription revenue flow and return FlowStatusPayload dict."""
        try:
            result = run_subscription_revenue_flow(
                gross_revenue=Decimal("1000.00"),
                participants=self._SAMPLE_REVENUE_PARTICIPANTS,
                tier=SubscriptionTier.STARTER,
                flow_id="probe_subscription",
            )
            e = result.evidence
            return FlowStatusPayload(
                flow_id=e.flow_id,
                flow_name=e.flow_name,
                status="success",
                allow_or_deny=e.allow_or_deny,
                input_hash=e.input_hash,
                output_hash=e.output_hash,
                proof_hash=e.proof_hash,
                determinism_hash=e.determinism_hash,
                policy_decisions=e.policy_decisions,
                timestamp_utc=e.timestamp_utc,
            ).to_dict()
        except PolicyViolationError as exc:
            return FlowStatusPayload(
                flow_id="probe_subscription",
                flow_name="subscription_revenue",
                status="denied",
                allow_or_deny="deny",
                input_hash="",
                output_hash="",
                proof_hash=None,
                determinism_hash="",
                policy_decisions=[exc.decision.to_evidence()],
                timestamp_utc=datetime.now(UTC).isoformat(),
            ).to_dict()
        except Exception as exc:
            return {"flow_name": "subscription_revenue", "status": "error", "error": str(exc)}

    def _probe_license_fee_flow(self) -> dict[str, Any]:
        """Probe license fee flow."""
        try:
            result = run_license_fee_flow(
                amount=Decimal("500.00"),
                license_type=LicenseType.COMMERCIAL,
                fee_participants=self._SAMPLE_FEE_PARTICIPANTS,
                flow_id="probe_license_fee",
            )
            e = result.evidence
            return FlowStatusPayload(
                flow_id=e.flow_id,
                flow_name=e.flow_name,
                status="success",
                allow_or_deny=e.allow_or_deny,
                input_hash=e.input_hash,
                output_hash=e.output_hash,
                proof_hash=e.proof_hash,
                determinism_hash=e.determinism_hash,
                policy_decisions=e.policy_decisions,
                timestamp_utc=e.timestamp_utc,
            ).to_dict()
        except PolicyViolationError as exc:
            return {"flow_name": "license_fee", "status": "denied", "error": exc.decision.reason}
        except Exception as exc:
            return {"flow_name": "license_fee", "status": "error", "error": str(exc)}

    def _probe_reward_governance_flow(self) -> dict[str, Any]:
        """Probe reward governance flow."""
        try:
            result = run_reward_governance_flow(
                reward_events=self._SAMPLE_REWARD_EVENTS,
                governance_pool=Decimal("200.00"),
                governance_participants=self._SAMPLE_GOVERNANCE_PARTICIPANTS,
                flow_id="probe_reward_governance",
            )
            e = result.evidence
            return FlowStatusPayload(
                flow_id=e.flow_id,
                flow_name=e.flow_name,
                status="success",
                allow_or_deny=e.allow_or_deny,
                input_hash=e.input_hash,
                output_hash=e.output_hash,
                proof_hash=e.proof_hash,
                determinism_hash=e.determinism_hash,
                policy_decisions=e.policy_decisions,
                timestamp_utc=e.timestamp_utc,
            ).to_dict()
        except PolicyViolationError as exc:
            return {"flow_name": "reward_governance", "status": "denied", "error": exc.decision.reason}
        except Exception as exc:
            return {"flow_name": "reward_governance", "status": "error", "error": str(exc)}

    def _probe_subscription_denied(self) -> dict[str, Any]:
        """Probe subscription flow with invalid input → expect DENY."""
        from decimal import Decimal as D  # noqa: N817

        from policy_enforcer import PolicyEnforcer, PolicyRule, PolicyRuleType

        # Use custom enforcer with very high MIN_POOL_AMOUNT to force deny
        # (subscription flow uses check_reward_distribution which checks MIN_POOL_AMOUNT)
        custom_enforcer = PolicyEnforcer(
            rules=[
                PolicyRule(PolicyRuleType.MAX_FEE, D("1000000"), "max fee cap"),
                PolicyRule(PolicyRuleType.MIN_PARTICIPANTS, 1, "min 1"),
                PolicyRule(PolicyRuleType.MIN_POOL_AMOUNT, D("9999999"), "very high minimum pool"),
                PolicyRule(PolicyRuleType.NON_NEGATIVE_AMOUNT, D("0"), "non-negative amount"),
                PolicyRule(PolicyRuleType.VALID_CURRENCY, {"USD", "EUR", "SSID", "BTC", "ETH"}, "valid currency"),
                PolicyRule(PolicyRuleType.MAX_GINI, 0.95, "max gini"),
            ]
        )
        try:
            run_subscription_revenue_flow(
                gross_revenue=D("1000.00"),  # below custom MIN_POOL_AMOUNT of 9999999 → DENY
                participants=self._SAMPLE_REVENUE_PARTICIPANTS,
                enforcer=custom_enforcer,
                flow_id="probe_subscription_denied",
            )
            return {"flow_name": "subscription_revenue", "status": "error", "error": "Expected DENY but got ALLOW"}
        except PolicyViolationError as exc:
            decision = exc.decision
            return {
                "flow_id": "probe_subscription_denied",
                "flow_name": "subscription_revenue",
                "status": "denied",
                "allow_or_deny": "deny",
                "input_hash": "",
                "output_hash": "",
                "proof_hash": None,
                "determinism_hash": "",
                "policy_decisions": [decision.to_evidence()],
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "error_reason": decision.reason,
            }

    def _module_health_with_degraded(self, degraded_module: str) -> list[dict[str, str]]:
        """Return module health list with one module marked as degraded."""
        from flow_evidence import MODULE_VERSIONS

        now = datetime.now(UTC).isoformat()
        return [
            ModuleHealthPayload(
                module_name=m,
                status="degraded" if m == degraded_module else "healthy",
                version=MODULE_VERSIONS.get(m, "1.0.0"),
                last_checked_utc=now,
            ).to_dict()
            for m in [
                "fee_distribution_engine",
                "subscription_revenue_distributor",
                "governance_reward_engine",
                "license_fee_splitter",
                "identity_fee_router",
                "reward_handler",
                "fee_proof_engine",
                "policy_enforcer",
            ]
        ]

    def generate_denied_report(self, flow_name: str = "subscription_revenue") -> SsidRuntimeReport:
        """Generate report where a policy check fails → denied flow status."""
        module_health = [m.to_dict() for m in get_module_health_payloads()]
        if flow_name == "subscription_revenue":
            flow_status = self._probe_subscription_denied()
        else:
            flow_status = {"flow_name": flow_name, "status": "denied", "allow_or_deny": "deny", "proof_hash": None}
        return SsidRuntimeReport(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now(UTC).isoformat(),
            module_health=module_health,
            flow_statuses=[flow_status],
        )

    def generate_degraded_report(self, degraded_module: str = "fee_proof_engine") -> SsidRuntimeReport:
        """Generate report with one module marked degraded."""
        module_health = self._module_health_with_degraded(degraded_module)
        flow_statuses = [
            self._probe_subscription_flow(),
            self._probe_license_fee_flow(),
            self._probe_reward_governance_flow(),
        ]
        return SsidRuntimeReport(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now(UTC).isoformat(),
            module_health=module_health,
            flow_statuses=flow_statuses,
        )

    def generate_report(self) -> SsidRuntimeReport:
        """Generate a full SSID runtime status report."""
        module_health = [m.to_dict() for m in get_module_health_payloads()]
        flow_statuses = [
            self._probe_subscription_flow(),
            self._probe_license_fee_flow(),
            self._probe_reward_governance_flow(),
        ]
        return SsidRuntimeReport(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now(UTC).isoformat(),
            module_health=module_health,
            flow_statuses=flow_statuses,
        )

    def export_to_file(self, output_path: str | Path) -> Path:
        """Generate report and atomically write to JSON file.

        Guarantees:
        - UTF-8 encoding
        - Stable key ordering (sort_keys=True)
        - Canonical JSON (no trailing spaces, consistent separators)
        - Atomic write (write to .tmp, then rename)
        - Returns the output file path
        """
        report = self.generate_report()
        path = Path(output_path)
        tmp_path = path.with_suffix(".tmp")
        canonical = json.dumps(report.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        tmp_path.write_text(canonical, encoding="utf-8")
        tmp_path.replace(path)  # atomic rename
        return path

    def export_report_with_hash(self, output_path: str | Path) -> tuple[Path, str]:
        """Export report to file and return (path, sha256_hash_of_content)."""
        import hashlib

        path = self.export_to_file(output_path)
        content = path.read_text(encoding="utf-8")
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return path, sha256
