"""Tests for 23_compliance.jurisdictions.eu_mica — MiCA compliance engine."""

import pathlib
import sys

sys.path.insert(
    0,
    str(pathlib.Path(__file__).resolve().parent.parent / "jurisdictions"),
)

from eu_mica import (
    WHITEPAPER_REQUIRED_SECTIONS,
    ComplianceStatus,
    MiCAComplianceEngine,
    MiCATokenType,
    WhitepaperStatus,
)

# ------------------------------------------------------------------
# Token Classification
# ------------------------------------------------------------------


class TestTokenClassification:
    def test_utility_token_default(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token("ssid_gov_token")
        assert result.token_type == MiCATokenType.UTILITY_TOKEN
        assert result.is_significant is False
        assert result.token_hash != ""

    def test_emt_classification(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token(
            "usd_stablecoin",
            has_payment_function=True,
            references_fiat=True,
            provides_access_to_service=False,
        )
        assert result.token_type == MiCATokenType.E_MONEY_TOKEN

    def test_art_classification(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token(
            "basket_token",
            has_payment_function=False,
            references_asset_basket=True,
            provides_access_to_service=False,
        )
        assert result.token_type == MiCATokenType.ASSET_REFERENCED_TOKEN

    def test_art_fiat_no_payment(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token(
            "eur_backed",
            has_payment_function=False,
            references_fiat=True,
            provides_access_to_service=False,
        )
        assert result.token_type == MiCATokenType.ASSET_REFERENCED_TOKEN

    def test_other_crypto_asset(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token(
            "misc_token",
            has_payment_function=False,
            references_fiat=False,
            references_asset_basket=False,
            provides_access_to_service=False,
        )
        assert result.token_type == MiCATokenType.OTHER_CRYPTO_ASSET

    def test_significant_emt(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token(
            "big_stablecoin",
            has_payment_function=True,
            references_fiat=True,
            daily_tx_volume=2_000_000,
        )
        assert result.token_type == MiCATokenType.E_MONEY_TOKEN
        assert result.is_significant is True

    def test_significant_art_by_holders(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token(
            "popular_art",
            references_asset_basket=True,
            provides_access_to_service=False,
            holder_count=15_000_000,
        )
        assert result.is_significant is True

    def test_classification_to_dict(self):
        engine = MiCAComplianceEngine()
        result = engine.classify_token("test_tok")
        d = result.to_dict()
        assert d["token_type"] == "utility_token"
        assert "classified_at" in d

    def test_ssid_utility_assertion(self):
        engine = MiCAComplianceEngine()
        result = engine.assert_ssid_utility_token("ssid_main")
        assert result.token_type == MiCATokenType.UTILITY_TOKEN
        assert result.is_significant is False


# ------------------------------------------------------------------
# Whitepaper Requirements
# ------------------------------------------------------------------


class TestWhitepaperRequirements:
    def test_all_sections_present(self):
        engine = MiCAComplianceEngine()
        result = engine.check_whitepaper("tok1", set(WHITEPAPER_REQUIRED_SECTIONS))
        assert result.status == WhitepaperStatus.APPROVED
        assert result.evidence_hash != ""

    def test_missing_sections_rejected(self):
        engine = MiCAComplianceEngine()
        present = {"project_description", "token_details"}
        result = engine.check_whitepaper("tok1", present)
        assert result.status == WhitepaperStatus.REJECTED

    def test_missing_sections_listed_in_dict(self):
        engine = MiCAComplianceEngine()
        present = {"project_description", "token_details"}
        result = engine.check_whitepaper("tok1", present)
        d = result.to_dict()
        assert len(d["missing_sections"]) > 0
        assert "risks" in d["missing_sections"]

    def test_empty_sections_rejected(self):
        engine = MiCAComplianceEngine()
        result = engine.check_whitepaper("tok1", set())
        assert result.status == WhitepaperStatus.REJECTED


# ------------------------------------------------------------------
# Reserve Requirements
# ------------------------------------------------------------------


class TestReserveRequirements:
    def test_emt_sufficient_reserve(self):
        engine = MiCAComplianceEngine()
        result = engine.check_reserve(
            "stable1",
            MiCATokenType.E_MONEY_TOKEN,
            1.05,
        )
        assert result.compliant is True
        assert result.reserve_ratio_required == 1.0

    def test_emt_insufficient_reserve(self):
        engine = MiCAComplianceEngine()
        result = engine.check_reserve(
            "stable2",
            MiCATokenType.E_MONEY_TOKEN,
            0.85,
        )
        assert result.compliant is False

    def test_art_sufficient_reserve(self):
        engine = MiCAComplianceEngine()
        result = engine.check_reserve(
            "art1",
            MiCATokenType.ASSET_REFERENCED_TOKEN,
            1.0,
        )
        assert result.compliant is True

    def test_utility_no_reserve_required(self):
        engine = MiCAComplianceEngine()
        result = engine.check_reserve(
            "util1",
            MiCATokenType.UTILITY_TOKEN,
            0.0,
        )
        assert result.compliant is True
        assert result.reserve_ratio_required == 0.0

    def test_reserve_to_dict(self):
        engine = MiCAComplianceEngine()
        result = engine.check_reserve(
            "tok1",
            MiCATokenType.E_MONEY_TOKEN,
            1.0,
        )
        d = result.to_dict()
        assert d["compliant"] is True
        assert d["token_type"] == "e_money_token"


# ------------------------------------------------------------------
# Overall Compliance Status
# ------------------------------------------------------------------


class TestComplianceStatus:
    def test_pending_when_not_classified(self):
        engine = MiCAComplianceEngine()
        assert engine.get_compliance_status("unknown") == ComplianceStatus.PENDING_REVIEW

    def test_compliant_utility_token(self):
        engine = MiCAComplianceEngine()
        engine.classify_token("ssid_tok")
        assert engine.get_compliance_status("ssid_tok") == ComplianceStatus.COMPLIANT

    def test_non_compliant_whitepaper(self):
        engine = MiCAComplianceEngine()
        engine.classify_token("tok1")
        engine.check_whitepaper("tok1", {"project_description"})
        assert engine.get_compliance_status("tok1") == ComplianceStatus.NON_COMPLIANT

    def test_non_compliant_reserve(self):
        engine = MiCAComplianceEngine()
        engine.classify_token(
            "emt1",
            has_payment_function=True,
            references_fiat=True,
        )
        engine.check_reserve("emt1", MiCATokenType.E_MONEY_TOKEN, 0.5)
        assert engine.get_compliance_status("emt1") == ComplianceStatus.NON_COMPLIANT
