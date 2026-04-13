"""EU MiCA (Markets in Crypto-Assets) compliance engine for SSID.

SAFE-FIX: Hash-only, non-custodial. No raw PII stored.
Implements:
  - Token classification rules (utility vs payment vs e-money)
  - Whitepaper requirements validation
  - Reserve requirements for stablecoins (ARTs / EMTs)
  - Issuer obligation checks

Reference: Regulation (EU) 2023/1114 (MiCA)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ======================================================================
# Token Classification (MiCA Title III / IV / V)
# ======================================================================


class MiCATokenType(Enum):
    """MiCA token classification per Title III-V."""

    UTILITY_TOKEN = "utility_token"  # Title V — utility tokens
    ASSET_REFERENCED_TOKEN = "asset_referenced_token"  # Title III — ARTs
    E_MONEY_TOKEN = "e_money_token"  # Title IV — EMTs
    OTHER_CRYPTO_ASSET = "other_crypto_asset"  # Catch-all
    EXEMPT = "exempt"  # Outside MiCA scope


class WhitepaperStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXEMPT = "exempt"


class ComplianceStatus(Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    EXEMPT = "exempt"


# ======================================================================
# Data Models
# ======================================================================


@dataclass(frozen=True)
class TokenClassification:
    """Result of classifying a token under MiCA."""

    token_hash: str  # SHA-256 of token identifier
    token_type: MiCATokenType
    is_significant: bool  # Art. 43 — significant ART/EMT thresholds
    rationale: str
    classified_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_hash": self.token_hash,
            "token_type": self.token_type.value,
            "is_significant": self.is_significant,
            "rationale": self.rationale,
            "classified_at": self.classified_at,
        }


@dataclass(frozen=True)
class WhitepaperRequirement:
    """MiCA Art. 6 whitepaper requirement check."""

    token_hash: str
    status: WhitepaperStatus
    required_sections: frozenset  # set of required section names
    present_sections: frozenset  # set of sections found
    evidence_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_hash": self.token_hash,
            "status": self.status.value,
            "required_sections": sorted(self.required_sections),
            "present_sections": sorted(self.present_sections),
            "missing_sections": sorted(self.required_sections - self.present_sections),
            "evidence_hash": self.evidence_hash,
        }


@dataclass(frozen=True)
class ReserveRequirement:
    """Stablecoin reserve requirement check (Art. 36 ART / Art. 52 EMT)."""

    token_hash: str
    token_type: MiCATokenType
    reserve_ratio_required: float  # e.g. 1.0 for 100 %
    reserve_ratio_actual: float
    compliant: bool
    evidence_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_hash": self.token_hash,
            "token_type": self.token_type.value,
            "reserve_ratio_required": self.reserve_ratio_required,
            "reserve_ratio_actual": self.reserve_ratio_actual,
            "compliant": self.compliant,
            "evidence_hash": self.evidence_hash,
        }


# ======================================================================
# Classification Signals
# ======================================================================

# SSID-relevant whitepaper sections per MiCA Art. 6
WHITEPAPER_REQUIRED_SECTIONS: frozenset = frozenset(
    {
        "project_description",
        "token_details",
        "rights_and_obligations",
        "underlying_technology",
        "risks",
        "issuer_information",
        "environmental_impact",
    }
)

# Significant ART/EMT thresholds (Art. 43)
SIGNIFICANT_ART_HOLDER_THRESHOLD = 10_000_000  # 10 M holders
SIGNIFICANT_ART_MARKET_CAP_EUR = 5_000_000_000  # EUR 5 B
SIGNIFICANT_EMT_TX_VOLUME_DAILY = 1_000_000  # 1 M transactions/day


# ======================================================================
# MiCA Compliance Engine
# ======================================================================


class MiCAComplianceEngine:
    """MiCA compliance rules engine.

    Non-custodial, hash-only.  SSID tokens are utility/governance —
    this engine validates classification and flags obligations.
    """

    def __init__(self) -> None:
        self._classifications: dict[str, TokenClassification] = {}
        self._whitepaper_checks: dict[str, WhitepaperRequirement] = {}
        self._reserve_checks: dict[str, ReserveRequirement] = {}

    # ------------------------------------------------------------------
    # Token Classification
    # ------------------------------------------------------------------

    def classify_token(
        self,
        token_id: str,
        *,
        has_payment_function: bool = False,
        references_fiat: bool = False,
        references_asset_basket: bool = False,
        provides_access_to_service: bool = True,
        holder_count: int = 0,
        market_cap_eur: float = 0.0,
        daily_tx_volume: int = 0,
    ) -> TokenClassification:
        """Classify a token under MiCA rules.

        Default signals match SSID's utility token profile.
        """
        token_hash = hashlib.sha256(token_id.encode()).hexdigest()

        # Classification logic per MiCA Titles III-V
        if references_fiat and has_payment_function:
            token_type = MiCATokenType.E_MONEY_TOKEN
            rationale = "References fiat currency with payment function → EMT (Title IV)"
            is_significant = (
                daily_tx_volume >= SIGNIFICANT_EMT_TX_VOLUME_DAILY or market_cap_eur >= SIGNIFICANT_ART_MARKET_CAP_EUR
            )
        elif references_asset_basket or references_fiat:
            token_type = MiCATokenType.ASSET_REFERENCED_TOKEN
            rationale = "References asset basket or fiat → ART (Title III)"
            is_significant = (
                holder_count >= SIGNIFICANT_ART_HOLDER_THRESHOLD or market_cap_eur >= SIGNIFICANT_ART_MARKET_CAP_EUR
            )
        elif provides_access_to_service:
            token_type = MiCATokenType.UTILITY_TOKEN
            rationale = "Provides access to service/goods → Utility token (Title V)"
            is_significant = False
        else:
            token_type = MiCATokenType.OTHER_CRYPTO_ASSET
            rationale = "Does not match ART/EMT/utility criteria"
            is_significant = False

        classification = TokenClassification(
            token_hash=token_hash,
            token_type=token_type,
            is_significant=is_significant,
            rationale=rationale,
        )
        self._classifications[token_hash] = classification
        return classification

    # ------------------------------------------------------------------
    # Whitepaper Validation
    # ------------------------------------------------------------------

    def check_whitepaper(
        self,
        token_id: str,
        present_sections: set[str],
    ) -> WhitepaperRequirement:
        """Validate whitepaper completeness against MiCA Art. 6 requirements."""
        token_hash = hashlib.sha256(token_id.encode()).hexdigest()
        present = frozenset(present_sections)
        missing = WHITEPAPER_REQUIRED_SECTIONS - present

        status = WhitepaperStatus.APPROVED if not missing else WhitepaperStatus.REJECTED

        evidence_payload = f"{token_hash}:{sorted(present)}:{sorted(missing)}"
        evidence_hash = hashlib.sha256(evidence_payload.encode()).hexdigest()

        req = WhitepaperRequirement(
            token_hash=token_hash,
            status=status,
            required_sections=WHITEPAPER_REQUIRED_SECTIONS,
            present_sections=present,
            evidence_hash=evidence_hash,
        )
        self._whitepaper_checks[token_hash] = req
        return req

    # ------------------------------------------------------------------
    # Reserve Requirements (ART / EMT)
    # ------------------------------------------------------------------

    def check_reserve(
        self,
        token_id: str,
        token_type: MiCATokenType,
        reserve_ratio_actual: float,
    ) -> ReserveRequirement:
        """Check stablecoin reserve backing ratio.

        ARTs and EMTs require >= 100 % reserve backing.
        Utility tokens are exempt.
        """
        token_hash = hashlib.sha256(token_id.encode()).hexdigest()

        if token_type in (
            MiCATokenType.ASSET_REFERENCED_TOKEN,
            MiCATokenType.E_MONEY_TOKEN,
        ):
            required = 1.0  # 100 %
            compliant = reserve_ratio_actual >= required
        else:
            # Utility tokens have no reserve requirement
            required = 0.0
            compliant = True

        evidence_payload = f"{token_hash}:{token_type.value}:{reserve_ratio_actual}:{required}"
        evidence_hash = hashlib.sha256(evidence_payload.encode()).hexdigest()

        req = ReserveRequirement(
            token_hash=token_hash,
            token_type=token_type,
            reserve_ratio_required=required,
            reserve_ratio_actual=reserve_ratio_actual,
            compliant=compliant,
            evidence_hash=evidence_hash,
        )
        self._reserve_checks[token_hash] = req
        return req

    # ------------------------------------------------------------------
    # SSID-Specific Utility Token Assertion
    # ------------------------------------------------------------------

    def assert_ssid_utility_token(self, token_id: str) -> TokenClassification:
        """Assert that an SSID token is correctly classified as utility.

        SSID tokens are utility/governance tokens:
        - No payment function
        - No fiat/asset reference
        - Provide access to identity verification service
        """
        return self.classify_token(
            token_id,
            has_payment_function=False,
            references_fiat=False,
            references_asset_basket=False,
            provides_access_to_service=True,
        )

    # ------------------------------------------------------------------
    # Overall Status
    # ------------------------------------------------------------------

    def get_compliance_status(self, token_id: str) -> ComplianceStatus:
        """Return the aggregate compliance status for a token."""
        token_hash = hashlib.sha256(token_id.encode()).hexdigest()

        classification = self._classifications.get(token_hash)
        if classification is None:
            return ComplianceStatus.PENDING_REVIEW

        # Utility tokens with no whitepaper issues are compliant
        if classification.token_type == MiCATokenType.UTILITY_TOKEN:
            wp = self._whitepaper_checks.get(token_hash)
            if wp and wp.status == WhitepaperStatus.REJECTED:
                return ComplianceStatus.NON_COMPLIANT
            return ComplianceStatus.COMPLIANT

        # ART/EMT must pass reserve check
        reserve = self._reserve_checks.get(token_hash)
        if reserve and not reserve.compliant:
            return ComplianceStatus.NON_COMPLIANT

        wp = self._whitepaper_checks.get(token_hash)
        if wp and wp.status == WhitepaperStatus.REJECTED:
            return ComplianceStatus.NON_COMPLIANT

        return ComplianceStatus.COMPLIANT
