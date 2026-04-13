"""Regulatory coverage matrix for SSID.

SAFE-FIX: No PII, no secrets. Pure mapping / gap-analysis logic.
Implements:
  - RegulatoryCoverageMatrix for EU/EEA/UK/CH/APAC/Americas
  - Per-jurisdiction requirement mapping
  - Gap analysis function
  - Evidence generation (hash-based)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ======================================================================
# Enums
# ======================================================================


class Region(Enum):
    EU = "eu"
    EEA = "eea"
    UK = "uk"
    CH = "ch"  # Switzerland
    APAC = "apac"
    AMERICAS = "americas"


class RegulationDomain(Enum):
    """Broad regulatory domain categories."""

    AML_KYC = "aml_kyc"
    DATA_PROTECTION = "data_protection"
    CRYPTO_ASSETS = "crypto_assets"
    DIGITAL_IDENTITY = "digital_identity"
    FINANCIAL_SERVICES = "financial_services"
    CYBERSECURITY = "cybersecurity"
    AI_GOVERNANCE = "ai_governance"
    CONSUMER_PROTECTION = "consumer_protection"


class CoverageLevel(Enum):
    """How well SSID covers a regulatory requirement."""

    FULL = "full"  # Fully addressed
    PARTIAL = "partial"  # Addressed with known gaps
    PLANNED = "planned"  # On roadmap, not yet implemented
    NOT_APPLICABLE = "n_a"  # Regulation does not apply to SSID
    GAP = "gap"  # Not addressed, action required


# ======================================================================
# Data Models
# ======================================================================


@dataclass(frozen=True)
class RegulatoryRequirement:
    """A single regulatory requirement for a jurisdiction."""

    regulation_id: str  # e.g. "GDPR", "MiCA", "AMLD6"
    article: str  # e.g. "Art. 17"
    description: str
    domain: RegulationDomain
    mandatory: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "regulation_id": self.regulation_id,
            "article": self.article,
            "description": self.description,
            "domain": self.domain.value,
            "mandatory": self.mandatory,
        }


@dataclass(frozen=True)
class JurisdictionMapping:
    """Maps a jurisdiction to its applicable requirements and SSID coverage."""

    jurisdiction: str  # ISO 3166-1 alpha-2 or region code
    region: Region
    requirements: frozenset[RegulatoryRequirement]
    coverage: dict[str, CoverageLevel]  # regulation_id → coverage level

    def gap_count(self) -> int:
        return sum(
            1
            for req in self.requirements
            if req.mandatory and self.coverage.get(req.regulation_id) == CoverageLevel.GAP
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "jurisdiction": self.jurisdiction,
            "region": self.region.value,
            "requirements": [r.to_dict() for r in sorted(self.requirements, key=lambda r: r.regulation_id)],
            "coverage": {k: v.value for k, v in self.coverage.items()},
            "gap_count": self.gap_count(),
        }


@dataclass
class GapAnalysisResult:
    """Result of a regulatory gap analysis."""

    jurisdiction: str
    total_requirements: int
    mandatory_requirements: int
    full_coverage: int
    partial_coverage: int
    gaps: list[RegulatoryRequirement]
    planned: list[RegulatoryRequirement]
    evidence_hash: str = ""
    analysed_at: float = field(default_factory=time.time)

    @property
    def coverage_ratio(self) -> float:
        if self.mandatory_requirements == 0:
            return 1.0
        return self.full_coverage / self.mandatory_requirements

    def to_dict(self) -> dict[str, Any]:
        return {
            "jurisdiction": self.jurisdiction,
            "total_requirements": self.total_requirements,
            "mandatory_requirements": self.mandatory_requirements,
            "full_coverage": self.full_coverage,
            "partial_coverage": self.partial_coverage,
            "gap_count": len(self.gaps),
            "gaps": [g.to_dict() for g in self.gaps],
            "planned_count": len(self.planned),
            "coverage_ratio": round(self.coverage_ratio, 4),
            "evidence_hash": self.evidence_hash,
            "analysed_at": self.analysed_at,
        }


# ======================================================================
# Built-in Requirement Sets
# ======================================================================

# EU/EEA requirements applicable to SSID
_EU_REQUIREMENTS: frozenset[RegulatoryRequirement] = frozenset(
    {
        RegulatoryRequirement(
            "GDPR", "Art. 5-11", "Lawful processing & data subject rights", RegulationDomain.DATA_PROTECTION
        ),
        RegulatoryRequirement("GDPR_ERASURE", "Art. 17", "Right to erasure", RegulationDomain.DATA_PROTECTION),
        RegulatoryRequirement("GDPR_PORTABILITY", "Art. 20", "Data portability", RegulationDomain.DATA_PROTECTION),
        RegulatoryRequirement(
            "MiCA", "Art. 3-15", "Crypto-asset classification & whitepaper", RegulationDomain.CRYPTO_ASSETS
        ),
        RegulatoryRequirement(
            "AMLD6", "Art. 1-5", "AML obligations for crypto-asset service providers", RegulationDomain.AML_KYC
        ),
        RegulatoryRequirement(
            "eIDAS2", "Art. 1-12", "EU Digital Identity Wallet interoperability", RegulationDomain.DIGITAL_IDENTITY
        ),
        RegulatoryRequirement("DORA", "Art. 1-10", "Digital operational resilience", RegulationDomain.CYBERSECURITY),
        RegulatoryRequirement("AI_ACT", "Art. 6-52", "AI system risk classification", RegulationDomain.AI_GOVERNANCE),
        RegulatoryRequirement("NIS2", "Art. 1-8", "Network and information security", RegulationDomain.CYBERSECURITY),
    }
)

# UK requirements
_UK_REQUIREMENTS: frozenset[RegulatoryRequirement] = frozenset(
    {
        RegulatoryRequirement(
            "UK_GDPR", "Part 2-4", "UK data protection post-Brexit", RegulationDomain.DATA_PROTECTION
        ),
        RegulatoryRequirement(
            "UK_FCA_CRYPTO", "PS23/6", "FCA crypto-asset promotions rules", RegulationDomain.CRYPTO_ASSETS
        ),
        RegulatoryRequirement("UK_MLR", "Reg. 2017/692", "Money Laundering Regulations", RegulationDomain.AML_KYC),
        RegulatoryRequirement(
            "UK_DIAT", "2025 Order", "Digital identity & attributes trust framework", RegulationDomain.DIGITAL_IDENTITY
        ),
    }
)

# Switzerland
_CH_REQUIREMENTS: frozenset[RegulatoryRequirement] = frozenset(
    {
        RegulatoryRequirement(
            "CH_DSG", "nDSG 2023", "Swiss Federal Data Protection Act", RegulationDomain.DATA_PROTECTION
        ),
        RegulatoryRequirement(
            "CH_DLT", "DLT Act 2021", "DLT trading facility framework", RegulationDomain.CRYPTO_ASSETS
        ),
        RegulatoryRequirement("CH_AMLA", "AMLA 2023", "Anti-money laundering act", RegulationDomain.AML_KYC),
    }
)

# APAC representative requirements
_APAC_REQUIREMENTS: frozenset[RegulatoryRequirement] = frozenset(
    {
        RegulatoryRequirement(
            "SG_PSA", "PSN02/2024", "Singapore Payment Services Act — DPT", RegulationDomain.CRYPTO_ASSETS
        ),
        RegulatoryRequirement(
            "HK_VATP", "SFC VATP", "Hong Kong virtual asset trading platform licensing", RegulationDomain.CRYPTO_ASSETS
        ),
        RegulatoryRequirement(
            "JP_PSA", "2023 Amend.", "Japan Payment Services Act — stablecoins", RegulationDomain.CRYPTO_ASSETS
        ),
        RegulatoryRequirement(
            "AU_AUSTRAC", "DCE Reg.", "Australia digital currency exchange registration", RegulationDomain.AML_KYC
        ),
        RegulatoryRequirement(
            "SG_PDPA", "PDPA 2012", "Singapore Personal Data Protection Act", RegulationDomain.DATA_PROTECTION
        ),
    }
)

# Americas representative requirements
_AMERICAS_REQUIREMENTS: frozenset[RegulatoryRequirement] = frozenset(
    {
        RegulatoryRequirement("US_OFAC", "31 CFR 501", "OFAC sanctions compliance", RegulationDomain.AML_KYC),
        RegulatoryRequirement("US_BSA", "31 USC 5311", "Bank Secrecy Act — AML/KYC", RegulationDomain.AML_KYC),
        RegulatoryRequirement(
            "US_IRS_1099DA", "IRS Final", "Digital asset reporting (1099-DA)", RegulationDomain.FINANCIAL_SERVICES
        ),
        RegulatoryRequirement("CA_FINTRAC", "LVCTR", "Canadian AML/ATF for virtual currency", RegulationDomain.AML_KYC),
        RegulatoryRequirement("BR_LGPD", "Lei 13.709", "Brazilian data protection", RegulationDomain.DATA_PROTECTION),
    }
)

# Default region → requirements mapping
DEFAULT_REGION_REQUIREMENTS: dict[Region, frozenset[RegulatoryRequirement]] = {
    Region.EU: _EU_REQUIREMENTS,
    Region.EEA: _EU_REQUIREMENTS,  # EEA adopts EU regulations
    Region.UK: _UK_REQUIREMENTS,
    Region.CH: _CH_REQUIREMENTS,
    Region.APAC: _APAC_REQUIREMENTS,
    Region.AMERICAS: _AMERICAS_REQUIREMENTS,
}

# Default SSID coverage — reflects current implementation state
DEFAULT_SSID_COVERAGE: dict[str, CoverageLevel] = {
    # EU
    "GDPR": CoverageLevel.FULL,
    "GDPR_ERASURE": CoverageLevel.FULL,
    "GDPR_PORTABILITY": CoverageLevel.FULL,
    "MiCA": CoverageLevel.FULL,
    "AMLD6": CoverageLevel.PARTIAL,
    "eIDAS2": CoverageLevel.PLANNED,
    "DORA": CoverageLevel.PARTIAL,
    "AI_ACT": CoverageLevel.PARTIAL,
    "NIS2": CoverageLevel.PARTIAL,
    # UK
    "UK_GDPR": CoverageLevel.FULL,
    "UK_FCA_CRYPTO": CoverageLevel.PARTIAL,
    "UK_MLR": CoverageLevel.PARTIAL,
    "UK_DIAT": CoverageLevel.PLANNED,
    # CH
    "CH_DSG": CoverageLevel.FULL,
    "CH_DLT": CoverageLevel.FULL,
    "CH_AMLA": CoverageLevel.PARTIAL,
    # APAC
    "SG_PSA": CoverageLevel.PARTIAL,
    "HK_VATP": CoverageLevel.PLANNED,
    "JP_PSA": CoverageLevel.PLANNED,
    "AU_AUSTRAC": CoverageLevel.PARTIAL,
    "SG_PDPA": CoverageLevel.FULL,
    # Americas
    "US_OFAC": CoverageLevel.FULL,
    "US_BSA": CoverageLevel.PARTIAL,
    "US_IRS_1099DA": CoverageLevel.PLANNED,
    "CA_FINTRAC": CoverageLevel.PARTIAL,
    "BR_LGPD": CoverageLevel.FULL,
}


# ======================================================================
# Regulatory Coverage Matrix
# ======================================================================


class RegulatoryCoverageMatrix:
    """Regulatory coverage matrix across all target jurisdictions.

    Provides per-region requirement mappings, coverage tracking,
    and gap analysis.
    """

    def __init__(
        self,
        coverage: dict[str, CoverageLevel] | None = None,
    ) -> None:
        self._coverage = dict(coverage or DEFAULT_SSID_COVERAGE)
        self._mappings: dict[str, JurisdictionMapping] = {}

    # ------------------------------------------------------------------
    # Mapping Management
    # ------------------------------------------------------------------

    def add_jurisdiction(
        self,
        jurisdiction: str,
        region: Region,
        requirements: set[RegulatoryRequirement] | None = None,
    ) -> JurisdictionMapping:
        """Register a jurisdiction with its requirements."""
        reqs = frozenset(requirements or DEFAULT_REGION_REQUIREMENTS.get(region, frozenset()))
        coverage_slice = {req.regulation_id: self._coverage.get(req.regulation_id, CoverageLevel.GAP) for req in reqs}
        mapping = JurisdictionMapping(
            jurisdiction=jurisdiction,
            region=region,
            requirements=reqs,
            coverage=coverage_slice,
        )
        self._mappings[jurisdiction] = mapping
        return mapping

    def get_jurisdiction(self, jurisdiction: str) -> JurisdictionMapping | None:
        return self._mappings.get(jurisdiction)

    def list_jurisdictions(self) -> list[str]:
        return sorted(self._mappings.keys())

    # ------------------------------------------------------------------
    # Coverage Updates
    # ------------------------------------------------------------------

    def update_coverage(
        self,
        regulation_id: str,
        level: CoverageLevel,
    ) -> None:
        """Update the coverage level for a regulation across all jurisdictions."""
        self._coverage[regulation_id] = level
        # Refresh mappings
        for jur_code, mapping in self._mappings.items():
            new_coverage = dict(mapping.coverage)
            if regulation_id in new_coverage:
                new_coverage[regulation_id] = level
            self._mappings[jur_code] = JurisdictionMapping(
                jurisdiction=mapping.jurisdiction,
                region=mapping.region,
                requirements=mapping.requirements,
                coverage=new_coverage,
            )

    # ------------------------------------------------------------------
    # Gap Analysis
    # ------------------------------------------------------------------

    def analyse_gaps(self, jurisdiction: str) -> GapAnalysisResult:
        """Run gap analysis for a specific jurisdiction."""
        mapping = self._mappings.get(jurisdiction)
        if mapping is None:
            raise KeyError(f"Unknown jurisdiction: {jurisdiction}")

        mandatory_reqs = [r for r in mapping.requirements if r.mandatory]
        gaps: list[RegulatoryRequirement] = []
        planned: list[RegulatoryRequirement] = []
        full = 0
        partial = 0

        for req in mandatory_reqs:
            level = mapping.coverage.get(req.regulation_id, CoverageLevel.GAP)
            if level == CoverageLevel.FULL:
                full += 1
            elif level == CoverageLevel.PARTIAL:
                partial += 1
            elif level == CoverageLevel.PLANNED:
                planned.append(req)
            elif level == CoverageLevel.GAP:
                gaps.append(req)

        evidence_payload = f"{jurisdiction}:{len(mandatory_reqs)}:{full}:{partial}:{len(gaps)}:{time.time()}"
        evidence_hash = hashlib.sha256(evidence_payload.encode()).hexdigest()

        return GapAnalysisResult(
            jurisdiction=jurisdiction,
            total_requirements=len(list(mapping.requirements)),
            mandatory_requirements=len(mandatory_reqs),
            full_coverage=full,
            partial_coverage=partial,
            gaps=gaps,
            planned=planned,
            evidence_hash=evidence_hash,
        )

    def analyse_all_gaps(self) -> dict[str, GapAnalysisResult]:
        """Run gap analysis across all registered jurisdictions."""
        return {jur: self.analyse_gaps(jur) for jur in self._mappings}

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def coverage_summary(self) -> dict[str, Any]:
        """Produce a summary of coverage across all jurisdictions."""
        all_gaps = self.analyse_all_gaps()
        total_mandatory = sum(r.mandatory_requirements for r in all_gaps.values())
        total_full = sum(r.full_coverage for r in all_gaps.values())
        total_gaps = sum(len(r.gaps) for r in all_gaps.values())

        return {
            "jurisdictions_registered": len(self._mappings),
            "total_mandatory_requirements": total_mandatory,
            "total_full_coverage": total_full,
            "total_gaps": total_gaps,
            "per_jurisdiction": {jur: result.to_dict() for jur, result in all_gaps.items()},
        }

    def get_regions_with_gaps(self) -> list[tuple[str, int]]:
        """Return jurisdictions that have mandatory gaps, sorted by gap count."""
        results: list[tuple[str, int]] = []
        for jur, mapping in self._mappings.items():
            gc = mapping.gap_count()
            if gc > 0:
                results.append((jur, gc))
        return sorted(results, key=lambda x: -x[1])
