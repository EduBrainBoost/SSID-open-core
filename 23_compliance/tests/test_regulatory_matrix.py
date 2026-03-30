"""Tests for 23_compliance.mappings.regulatory_matrix."""

import pathlib
import sys

import pytest

sys.path.insert(
    0,
    str(pathlib.Path(__file__).resolve().parent.parent / "mappings"),
)

from regulatory_matrix import (
    CoverageLevel,
    DEFAULT_SSID_COVERAGE,
    GapAnalysisResult,
    JurisdictionMapping,
    Region,
    RegulationDomain,
    RegulatoryCoverageMatrix,
    RegulatoryRequirement,
)


# ------------------------------------------------------------------
# RegulatoryRequirement
# ------------------------------------------------------------------

class TestRegulatoryRequirement:
    def test_to_dict(self):
        req = RegulatoryRequirement(
            regulation_id="GDPR",
            article="Art. 17",
            description="Right to erasure",
            domain=RegulationDomain.DATA_PROTECTION,
        )
        d = req.to_dict()
        assert d["regulation_id"] == "GDPR"
        assert d["domain"] == "data_protection"
        assert d["mandatory"] is True

    def test_frozen(self):
        req = RegulatoryRequirement(
            regulation_id="X", article="1",
            description="d", domain=RegulationDomain.AML_KYC,
        )
        with pytest.raises(AttributeError):
            req.regulation_id = "Y"  # type: ignore[misc]


# ------------------------------------------------------------------
# RegulatoryCoverageMatrix — Jurisdiction Management
# ------------------------------------------------------------------

class TestMatrixJurisdictions:
    def test_add_jurisdiction_eu(self):
        matrix = RegulatoryCoverageMatrix()
        mapping = matrix.add_jurisdiction("DE", Region.EU)
        assert mapping.jurisdiction == "DE"
        assert mapping.region == Region.EU
        assert len(mapping.requirements) > 0

    def test_add_jurisdiction_uk(self):
        matrix = RegulatoryCoverageMatrix()
        mapping = matrix.add_jurisdiction("GB", Region.UK)
        assert mapping.region == Region.UK

    def test_add_jurisdiction_ch(self):
        matrix = RegulatoryCoverageMatrix()
        mapping = matrix.add_jurisdiction("CH", Region.CH)
        assert mapping.region == Region.CH

    def test_add_jurisdiction_apac(self):
        matrix = RegulatoryCoverageMatrix()
        mapping = matrix.add_jurisdiction("SG", Region.APAC)
        assert mapping.region == Region.APAC

    def test_add_jurisdiction_americas(self):
        matrix = RegulatoryCoverageMatrix()
        mapping = matrix.add_jurisdiction("US", Region.AMERICAS)
        assert mapping.region == Region.AMERICAS

    def test_list_jurisdictions(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        matrix.add_jurisdiction("US", Region.AMERICAS)
        jurs = matrix.list_jurisdictions()
        assert jurs == ["DE", "US"]

    def test_get_jurisdiction(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        mapping = matrix.get_jurisdiction("DE")
        assert mapping is not None
        assert mapping.jurisdiction == "DE"

    def test_get_unknown_jurisdiction(self):
        matrix = RegulatoryCoverageMatrix()
        assert matrix.get_jurisdiction("XX") is None

    def test_custom_requirements(self):
        matrix = RegulatoryCoverageMatrix()
        custom = {RegulatoryRequirement(
            "CUSTOM_REG", "Sec. 1", "Custom regulation",
            RegulationDomain.CRYPTO_ASSETS,
        )}
        mapping = matrix.add_jurisdiction("XX", Region.EU, requirements=custom)
        assert len(mapping.requirements) == 1

    def test_eea_uses_eu_requirements(self):
        matrix = RegulatoryCoverageMatrix()
        eu_mapping = matrix.add_jurisdiction("DE", Region.EU)
        eea_mapping = matrix.add_jurisdiction("NO", Region.EEA)
        assert eu_mapping.requirements == eea_mapping.requirements


# ------------------------------------------------------------------
# Coverage Updates
# ------------------------------------------------------------------

class TestCoverageUpdates:
    def test_update_coverage(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        matrix.update_coverage("eIDAS2", CoverageLevel.FULL)
        mapping = matrix.get_jurisdiction("DE")
        assert mapping is not None
        assert mapping.coverage["eIDAS2"] == CoverageLevel.FULL

    def test_default_coverage_applied(self):
        matrix = RegulatoryCoverageMatrix()
        mapping = matrix.add_jurisdiction("DE", Region.EU)
        # GDPR should be FULL per defaults
        assert mapping.coverage.get("GDPR") == CoverageLevel.FULL


# ------------------------------------------------------------------
# Gap Analysis
# ------------------------------------------------------------------

class TestGapAnalysis:
    def test_analyse_gaps_eu(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        result = matrix.analyse_gaps("DE")
        assert result.jurisdiction == "DE"
        assert result.total_requirements > 0
        assert result.mandatory_requirements > 0
        assert result.full_coverage > 0
        assert result.evidence_hash != ""

    def test_analyse_gaps_unknown_raises(self):
        matrix = RegulatoryCoverageMatrix()
        with pytest.raises(KeyError):
            matrix.analyse_gaps("XX")

    def test_analyse_all_gaps(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        matrix.add_jurisdiction("US", Region.AMERICAS)
        results = matrix.analyse_all_gaps()
        assert "DE" in results
        assert "US" in results

    def test_coverage_ratio(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        result = matrix.analyse_gaps("DE")
        assert 0.0 <= result.coverage_ratio <= 1.0

    def test_gap_analysis_to_dict(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        result = matrix.analyse_gaps("DE")
        d = result.to_dict()
        assert "coverage_ratio" in d
        assert "gaps" in d
        assert isinstance(d["gaps"], list)

    def test_gaps_with_all_coverage_full(self):
        # All requirements covered → no gaps
        custom = {RegulatoryRequirement(
            "TEST_REG", "Art. 1", "Test",
            RegulationDomain.DATA_PROTECTION,
        )}
        coverage = {"TEST_REG": CoverageLevel.FULL}
        matrix = RegulatoryCoverageMatrix(coverage=coverage)
        matrix.add_jurisdiction("XX", Region.EU, requirements=custom)
        result = matrix.analyse_gaps("XX")
        assert len(result.gaps) == 0
        assert result.coverage_ratio == 1.0

    def test_gaps_with_missing_coverage(self):
        custom = {RegulatoryRequirement(
            "MISSING_REG", "Art. 1", "Not covered",
            RegulationDomain.AML_KYC,
        )}
        matrix = RegulatoryCoverageMatrix(coverage={})
        matrix.add_jurisdiction("XX", Region.EU, requirements=custom)
        result = matrix.analyse_gaps("XX")
        assert len(result.gaps) == 1
        assert result.coverage_ratio == 0.0


# ------------------------------------------------------------------
# Summary & Regions with Gaps
# ------------------------------------------------------------------

class TestSummary:
    def test_coverage_summary(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        matrix.add_jurisdiction("US", Region.AMERICAS)
        summary = matrix.coverage_summary()
        assert summary["jurisdictions_registered"] == 2
        assert "per_jurisdiction" in summary
        assert "DE" in summary["per_jurisdiction"]

    def test_regions_with_gaps(self):
        matrix = RegulatoryCoverageMatrix()
        matrix.add_jurisdiction("DE", Region.EU)
        gaps = matrix.get_regions_with_gaps()
        # Should return list of (jurisdiction, gap_count) tuples
        assert isinstance(gaps, list)
        for jur, count in gaps:
            assert isinstance(jur, str)
            assert isinstance(count, int)
            assert count > 0


# ------------------------------------------------------------------
# JurisdictionMapping
# ------------------------------------------------------------------

class TestJurisdictionMapping:
    def test_gap_count(self):
        req = RegulatoryRequirement(
            "GAP_REG", "Art. 1", "Gap",
            RegulationDomain.AML_KYC, mandatory=True,
        )
        mapping = JurisdictionMapping(
            jurisdiction="XX",
            region=Region.EU,
            requirements=frozenset({req}),
            coverage={"GAP_REG": CoverageLevel.GAP},
        )
        assert mapping.gap_count() == 1

    def test_gap_count_zero(self):
        req = RegulatoryRequirement(
            "FULL_REG", "Art. 1", "Full",
            RegulationDomain.AML_KYC, mandatory=True,
        )
        mapping = JurisdictionMapping(
            jurisdiction="XX",
            region=Region.EU,
            requirements=frozenset({req}),
            coverage={"FULL_REG": CoverageLevel.FULL},
        )
        assert mapping.gap_count() == 0

    def test_to_dict(self):
        req = RegulatoryRequirement(
            "REG1", "Art. 1", "Desc",
            RegulationDomain.DATA_PROTECTION,
        )
        mapping = JurisdictionMapping(
            jurisdiction="DE",
            region=Region.EU,
            requirements=frozenset({req}),
            coverage={"REG1": CoverageLevel.FULL},
        )
        d = mapping.to_dict()
        assert d["jurisdiction"] == "DE"
        assert d["region"] == "eu"
