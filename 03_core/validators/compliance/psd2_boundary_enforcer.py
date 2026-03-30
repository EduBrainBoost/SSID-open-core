"""
PSD2 Boundary Enforcer (SWARM-03 / GAP-F010)

Validates that SSID operates strictly outside PSD2 scope by enforcing:

- No payment service operations (SSID is identity-only)
- Utility-only token usage (no e-money, no payment instruments)
- No custody of funds (non-custodial for financial assets)
- No payment initiation or account information services

SSID tokens are utility tokens for identity verification purposes only.
They do NOT constitute e-money, payment instruments, or financial products.

References:
    PSD2 (EU) 2015/2366
    MiCA (EU) 2023/1114 — utility token classification
    23_compliance/frameworks/mica/mica_controls.yaml
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PSD2ViolationType(Enum):
    """PSD2 boundary violation categories."""

    PAYMENT_SERVICE_DETECTED = "payment_service_detected"
    NON_UTILITY_TOKEN = "non_utility_token_usage"
    FUND_CUSTODY = "fund_custody_detected"
    PAYMENT_INITIATION = "payment_initiation_detected"
    ACCOUNT_INFO_SERVICE = "account_information_service_detected"
    E_MONEY_PATTERN = "e_money_pattern_detected"


@dataclass(frozen=True)
class PSD2Violation:
    """Single PSD2 boundary violation."""

    violation_type: str
    regulation: str
    field_or_operation: str
    detail: str
    remedy: str
    severity: str = "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_type": self.violation_type,
            "regulation": self.regulation,
            "field_or_operation": self.field_or_operation,
            "detail": self.detail,
            "remedy": self.remedy,
            "severity": self.severity,
        }


@dataclass
class PSD2EnforcementResult:
    """Result of a PSD2 boundary enforcement check."""

    passed: bool
    violations: List[PSD2Violation] = field(default_factory=list)
    enforcer: str = "PSD2BoundaryEnforcer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "enforcer": self.enforcer,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
        }


# SSID utility token purposes — the ONLY valid token use cases
VALID_UTILITY_PURPOSES = frozenset({
    "identity_verification",
    "credential_proof",
    "reputation_score",
    "skill_attestation",
    "access_grant",
    "governance_vote",
    "platform_fee",
    "staking_collateral",
})


class PSD2BoundaryEnforcer:
    """Validates that SSID stays outside PSD2 regulated scope.

    SSID is an identity and reputation platform. It must NEVER:
    - Process payments
    - Hold funds in custody
    - Issue e-money
    - Provide payment initiation services (PIS)
    - Provide account information services (AIS)

    Implements enforcement for:
        - GAP-F010: PSD2 Enforcer
    """

    # Operations that would bring SSID into PSD2 scope
    FORBIDDEN_PAYMENT_OPERATIONS: List[str] = [
        "process_payment",
        "initiate_transfer",
        "debit_account",
        "credit_account",
        "hold_funds",
        "escrow_payment",
        "refund_payment",
        "settle_transaction",
        "clear_payment",
        "authorize_payment",
        "capture_payment",
        "release_funds",
        "withdraw_funds",
        "deposit_funds",
    ]

    # Patterns indicating payment initiation (PIS)
    PAYMENT_INITIATION_PATTERNS: List[str] = [
        "initiate_payment",
        "create_payment_order",
        "submit_payment",
        "execute_transfer",
        "send_money",
        "wire_transfer",
    ]

    # Patterns indicating account information services (AIS)
    AIS_PATTERNS: List[str] = [
        "fetch_balance",
        "get_account_balance",
        "list_transactions",
        "aggregate_accounts",
        "read_bank_account",
        "get_payment_history",
    ]

    # E-money indicators
    E_MONEY_PATTERNS: List[str] = [
        "issue_emoney",
        "e_money",
        "electronic_money",
        "stored_value",
        "prepaid_balance",
        "fiat_token",
        "stablecoin_issue",
    ]

    def validate_no_payment_services(self, operation: str) -> PSD2EnforcementResult:
        """Validate that no payment service operations exist.

        Args:
            operation: The operation identifier to check.

        Returns:
            PSD2EnforcementResult with payment service violations.
        """
        violations: List[PSD2Violation] = []
        op_lower = operation.lower()

        for pattern in self.FORBIDDEN_PAYMENT_OPERATIONS:
            if pattern in op_lower:
                violations.append(PSD2Violation(
                    violation_type=PSD2ViolationType.PAYMENT_SERVICE_DETECTED.value,
                    regulation="PSD2 Art. 4(3)",
                    field_or_operation=operation,
                    detail=f"Payment service pattern '{pattern}' detected in operation",
                    remedy="SSID must not process payments; remove payment functionality",
                ))

        for pattern in self.PAYMENT_INITIATION_PATTERNS:
            if pattern in op_lower:
                violations.append(PSD2Violation(
                    violation_type=PSD2ViolationType.PAYMENT_INITIATION.value,
                    regulation="PSD2 Art. 4(15)",
                    field_or_operation=operation,
                    detail=f"Payment initiation pattern '{pattern}' detected",
                    remedy="SSID must not initiate payments; this requires PIS license",
                ))

        for pattern in self.AIS_PATTERNS:
            if pattern in op_lower:
                violations.append(PSD2Violation(
                    violation_type=PSD2ViolationType.ACCOUNT_INFO_SERVICE.value,
                    regulation="PSD2 Art. 4(16)",
                    field_or_operation=operation,
                    detail=f"Account information service pattern '{pattern}' detected",
                    remedy="SSID must not aggregate bank accounts; this requires AIS license",
                ))

        for pattern in self.E_MONEY_PATTERNS:
            if pattern in op_lower:
                violations.append(PSD2Violation(
                    violation_type=PSD2ViolationType.E_MONEY_PATTERN.value,
                    regulation="EMD2 Art. 2(2)",
                    field_or_operation=operation,
                    detail=f"E-money pattern '{pattern}' detected",
                    remedy="SSID tokens are utility tokens; e-money issuance requires EMI license",
                ))

        return PSD2EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_utility_only_token(self, token_metadata: Dict[str, Any]) -> PSD2EnforcementResult:
        """Validate that token usage is strictly utility-only.

        Args:
            token_metadata: Must contain 'purpose' and optionally 'redeemable_for_fiat'.

        Returns:
            PSD2EnforcementResult with token classification violations.
        """
        violations: List[PSD2Violation] = []

        purpose = token_metadata.get("purpose", "")
        if purpose and purpose not in VALID_UTILITY_PURPOSES:
            violations.append(PSD2Violation(
                violation_type=PSD2ViolationType.NON_UTILITY_TOKEN.value,
                regulation="MiCA Art. 3(1)(5)",
                field_or_operation="token_metadata.purpose",
                detail=f"Token purpose '{purpose}' is not a valid utility purpose",
                remedy=f"Use one of: {', '.join(sorted(VALID_UTILITY_PURPOSES))}",
            ))

        if token_metadata.get("redeemable_for_fiat", False):
            violations.append(PSD2Violation(
                violation_type=PSD2ViolationType.E_MONEY_PATTERN.value,
                regulation="MiCA Art. 3(1)(7)",
                field_or_operation="token_metadata.redeemable_for_fiat",
                detail="Token marked as redeemable for fiat currency (e-money characteristic)",
                remedy="SSID utility tokens must NOT be redeemable for fiat",
            ))

        if token_metadata.get("represents_funds", False):
            violations.append(PSD2Violation(
                violation_type=PSD2ViolationType.FUND_CUSTODY.value,
                regulation="PSD2 Art. 4(25)",
                field_or_operation="token_metadata.represents_funds",
                detail="Token represents funds (custody of funds detected)",
                remedy="SSID tokens must not represent or custody funds",
            ))

        return PSD2EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def validate_no_fund_custody(self, operation: str, params: Optional[Dict] = None) -> PSD2EnforcementResult:
        """Validate that no custody of funds occurs.

        Args:
            operation: The operation identifier.
            params: Optional parameters to check for fund custody indicators.

        Returns:
            PSD2EnforcementResult with fund custody violations.
        """
        violations: List[PSD2Violation] = []

        custody_patterns = [
            "hold_funds", "escrow", "custody_balance", "safeguard_funds",
            "client_money", "segregated_account", "omnibus_account",
        ]

        op_lower = operation.lower()
        for pattern in custody_patterns:
            if pattern in op_lower:
                violations.append(PSD2Violation(
                    violation_type=PSD2ViolationType.FUND_CUSTODY.value,
                    regulation="PSD2 Art. 10",
                    field_or_operation=operation,
                    detail=f"Fund custody pattern '{pattern}' detected",
                    remedy="SSID is non-custodial; remove fund custody operations",
                ))

        if params:
            for key in params:
                key_lower = key.lower()
                if any(ind in key_lower for ind in ["balance", "funds", "amount", "currency"]):
                    if any(ind in key_lower for ind in ["hold", "custody", "escrow", "safeguard"]):
                        violations.append(PSD2Violation(
                            violation_type=PSD2ViolationType.FUND_CUSTODY.value,
                            regulation="PSD2 Art. 10",
                            field_or_operation=key,
                            detail=f"Parameter '{key}' indicates fund custody",
                            remedy="Remove fund-related parameters; SSID does not handle funds",
                        ))

        return PSD2EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def enforce_all(
        self,
        operation: str,
        token_metadata: Optional[Dict[str, Any]] = None,
        params: Optional[Dict] = None,
    ) -> PSD2EnforcementResult:
        """Run all PSD2 boundary checks and return combined result.

        Args:
            operation: Operation identifier.
            token_metadata: Optional token metadata to validate.
            params: Optional operation parameters.

        Returns:
            Combined PSD2EnforcementResult.
        """
        all_violations: List[PSD2Violation] = []

        payment_result = self.validate_no_payment_services(operation)
        all_violations.extend(payment_result.violations)

        if token_metadata:
            token_result = self.validate_utility_only_token(token_metadata)
            all_violations.extend(token_result.violations)

        custody_result = self.validate_no_fund_custody(operation, params)
        all_violations.extend(custody_result.violations)

        return PSD2EnforcementResult(
            passed=len(all_violations) == 0,
            violations=all_violations,
        )
