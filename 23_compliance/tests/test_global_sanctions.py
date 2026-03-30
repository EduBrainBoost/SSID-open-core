"""Tests for 23_compliance.jurisdictions.global_sanctions."""

import pathlib
import sys
import time

import pytest

sys.path.insert(
    0,
    str(pathlib.Path(__file__).resolve().parent.parent / "jurisdictions"),
)

from global_sanctions import (
    BLACKLISTED_JURISDICTIONS,
    GlobalSanctionsEngine,
    HIGH_RISK_JURISDICTIONS,
    MAX_STALENESS_SECONDS,
    RiskLevel,
    SanctionsListMetadata,
    SanctionsListSource,
    ScreeningReport,
    ScreeningResult,
)


# ------------------------------------------------------------------
# List Management
# ------------------------------------------------------------------

class TestListManagement:
    def test_load_list(self):
        engine = GlobalSanctionsEngine()
        h1 = GlobalSanctionsEngine.hash_entity("bad_actor")
        meta = engine.load_list(SanctionsListSource.OFAC_SDN, {h1})
        assert meta.source == SanctionsListSource.OFAC_SDN
        assert meta.entry_count == 1
        assert meta.list_hash != ""
        assert meta.is_stale is False

    def test_load_empty_list(self):
        engine = GlobalSanctionsEngine()
        meta = engine.load_list(SanctionsListSource.EU_CONSOLIDATED, set())
        assert meta.entry_count == 0

    def test_get_list_metadata(self):
        engine = GlobalSanctionsEngine()
        engine.load_list(SanctionsListSource.OFAC_SDN, {"h1"})
        meta = engine.get_list_metadata(SanctionsListSource.OFAC_SDN)
        assert meta is not None
        assert meta.source == SanctionsListSource.OFAC_SDN

    def test_get_unknown_metadata_none(self):
        engine = GlobalSanctionsEngine()
        assert engine.get_list_metadata(SanctionsListSource.UK_OFSI) is None

    def test_staleness_detection(self):
        engine = GlobalSanctionsEngine()
        engine.load_list(SanctionsListSource.OFAC_SDN, {"h1"})
        staleness = engine.check_staleness()
        assert staleness[SanctionsListSource.OFAC_SDN] is False

    def test_metadata_to_dict(self):
        engine = GlobalSanctionsEngine()
        meta = engine.load_list(SanctionsListSource.OFAC_SDN, {"h1"})
        d = meta.to_dict()
        assert d["source"] == "ofac_sdn"
        assert "is_stale" in d


# ------------------------------------------------------------------
# Entity Screening
# ------------------------------------------------------------------

class TestEntityScreening:
    def test_no_lists_loaded_blocks(self):
        engine = GlobalSanctionsEngine()
        report = engine.screen_entity("anyone")
        assert report.risk_level == RiskLevel.BLOCK
        assert report.result == ScreeningResult.STALE_DATA

    def test_match_blocks(self):
        engine = GlobalSanctionsEngine()
        h = GlobalSanctionsEngine.hash_entity("sanctioned_person")
        engine.load_list(SanctionsListSource.OFAC_SDN, {h})
        report = engine.screen_entity("sanctioned_person")
        assert report.result == ScreeningResult.MATCH
        assert report.risk_level == RiskLevel.BLOCK
        assert len(report.matched_sources) == 1

    def test_clear(self):
        engine = GlobalSanctionsEngine()
        h = GlobalSanctionsEngine.hash_entity("bad_actor")
        engine.load_list(SanctionsListSource.OFAC_SDN, {h})
        report = engine.screen_entity("good_actor")
        assert report.result == ScreeningResult.CLEAR
        assert report.risk_level == RiskLevel.CLEAR

    def test_case_insensitive_match(self):
        engine = GlobalSanctionsEngine()
        h = GlobalSanctionsEngine.hash_entity("john doe")
        engine.load_list(SanctionsListSource.OFAC_SDN, {h})
        report = engine.screen_entity("John Doe")
        assert report.result == ScreeningResult.MATCH

    def test_multi_list_match(self):
        engine = GlobalSanctionsEngine()
        h = GlobalSanctionsEngine.hash_entity("target")
        engine.load_list(SanctionsListSource.OFAC_SDN, {h})
        engine.load_list(SanctionsListSource.EU_CONSOLIDATED, {h})
        report = engine.screen_entity("target")
        assert report.result == ScreeningResult.MATCH
        assert len(report.matched_sources) == 2

    def test_no_raw_pii_in_report(self):
        engine = GlobalSanctionsEngine()
        h = GlobalSanctionsEngine.hash_entity("sensitive_name")
        engine.load_list(SanctionsListSource.OFAC_SDN, {h})
        report = engine.screen_entity("sensitive_name")
        assert "sensitive_name" not in report.detail

    def test_report_to_dict(self):
        engine = GlobalSanctionsEngine()
        engine.load_list(SanctionsListSource.OFAC_SDN, set())
        report = engine.screen_entity("test")
        d = report.to_dict()
        assert d["result"] == "clear"
        assert "screened_at" in d

    def test_hash_entity_deterministic(self):
        h1 = GlobalSanctionsEngine.hash_entity("test")
        h2 = GlobalSanctionsEngine.hash_entity("test")
        assert h1 == h2
        assert len(h1) == 64


# ------------------------------------------------------------------
# Jurisdiction Screening
# ------------------------------------------------------------------

class TestJurisdictionScreening:
    def test_blacklisted_blocks(self):
        engine = GlobalSanctionsEngine()
        for code in BLACKLISTED_JURISDICTIONS:
            report = engine.screen_jurisdiction(code)
            assert report.result == ScreeningResult.BLACKLISTED_JURISDICTION
            assert report.risk_level == RiskLevel.BLOCK

    def test_high_risk(self):
        engine = GlobalSanctionsEngine()
        for code in HIGH_RISK_JURISDICTIONS:
            report = engine.screen_jurisdiction(code)
            assert report.result == ScreeningResult.HIGH_RISK_JURISDICTION
            assert report.risk_level == RiskLevel.HIGH

    def test_clear_jurisdiction(self):
        engine = GlobalSanctionsEngine()
        report = engine.screen_jurisdiction("DE")
        assert report.result == ScreeningResult.CLEAR
        assert report.risk_level == RiskLevel.CLEAR

    def test_case_insensitive_code(self):
        engine = GlobalSanctionsEngine()
        report = engine.screen_jurisdiction("ir")
        assert report.result == ScreeningResult.BLACKLISTED_JURISDICTION

    def test_whitespace_handling(self):
        engine = GlobalSanctionsEngine()
        report = engine.screen_jurisdiction("  KP  ")
        assert report.result == ScreeningResult.BLACKLISTED_JURISDICTION

    def test_all_blacklisted_present(self):
        assert "IR" in BLACKLISTED_JURISDICTIONS
        assert "KP" in BLACKLISTED_JURISDICTIONS
        assert "SY" in BLACKLISTED_JURISDICTIONS
        assert "CU" in BLACKLISTED_JURISDICTIONS


# ------------------------------------------------------------------
# Full Screening (Entity + Jurisdiction)
# ------------------------------------------------------------------

class TestFullScreening:
    def test_combined_reports(self):
        engine = GlobalSanctionsEngine()
        engine.load_list(SanctionsListSource.OFAC_SDN, set())
        reports = engine.full_screening("clean_person", "DE")
        assert len(reports) == 2
        assert reports[0].result == ScreeningResult.CLEAR
        assert reports[1].result == ScreeningResult.CLEAR

    def test_entity_match_plus_clear_jurisdiction(self):
        engine = GlobalSanctionsEngine()
        h = GlobalSanctionsEngine.hash_entity("bad")
        engine.load_list(SanctionsListSource.OFAC_SDN, {h})
        reports = engine.full_screening("bad", "DE")
        assert reports[0].result == ScreeningResult.MATCH
        assert reports[1].result == ScreeningResult.CLEAR

    def test_clean_entity_plus_blacklisted_jurisdiction(self):
        engine = GlobalSanctionsEngine()
        engine.load_list(SanctionsListSource.OFAC_SDN, set())
        reports = engine.full_screening("clean", "IR")
        assert reports[0].result == ScreeningResult.CLEAR
        assert reports[1].result == ScreeningResult.BLACKLISTED_JURISDICTION


# ------------------------------------------------------------------
# Staleness Enforcement
# ------------------------------------------------------------------

class TestStaleness:
    def test_fresh_list_not_stale(self):
        meta = SanctionsListMetadata(
            source=SanctionsListSource.OFAC_SDN,
            entry_count=100,
            loaded_at=time.time(),
            list_hash="abc",
        )
        assert meta.is_stale is False

    def test_old_list_is_stale(self):
        meta = SanctionsListMetadata(
            source=SanctionsListSource.OFAC_SDN,
            entry_count=100,
            loaded_at=time.time() - MAX_STALENESS_SECONDS - 1,
            list_hash="abc",
        )
        assert meta.is_stale is True

    def test_has_stale_lists_flag(self):
        engine = GlobalSanctionsEngine()
        # Manually inject stale metadata
        engine._metadata[SanctionsListSource.OFAC_SDN] = SanctionsListMetadata(
            source=SanctionsListSource.OFAC_SDN,
            entry_count=1,
            loaded_at=time.time() - MAX_STALENESS_SECONDS - 1,
            list_hash="old",
        )
        engine._lists[SanctionsListSource.OFAC_SDN] = set()
        assert engine.has_stale_lists() is True

    def test_stale_data_blocks_screening(self):
        engine = GlobalSanctionsEngine()
        engine._metadata[SanctionsListSource.OFAC_SDN] = SanctionsListMetadata(
            source=SanctionsListSource.OFAC_SDN,
            entry_count=1,
            loaded_at=time.time() - MAX_STALENESS_SECONDS - 1,
            list_hash="old",
        )
        engine._lists[SanctionsListSource.OFAC_SDN] = set()
        report = engine.screen_entity("anyone")
        assert report.result == ScreeningResult.STALE_DATA
        assert report.risk_level == RiskLevel.BLOCK
