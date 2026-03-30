"""Global sanctions screening framework for SSID.

SAFE-FIX: Hash-only, non-custodial. No raw PII or sanctions list data stored.
Implements:
  - OFAC SDN list integration (hash-based, no raw data)
  - EU consolidated sanctions list
  - Jurisdiction blacklist (IR, KP, SY, CU)
  - Max 24 h staleness enforcement
  - Evidence generation

References:
  - OFAC SDN List (31 CFR Part 501)
  - EU Council Regulation (EC) No 881/2002 et seq.
  - UN Security Council Consolidated List
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set


# ======================================================================
# Constants
# ======================================================================

# Maximum staleness for sanctions data: 24 hours
MAX_STALENESS_SECONDS = 24 * 3600

# ISO 3166-1 alpha-2 codes for jurisdictions with comprehensive sanctions
# (OFAC, EU, UN). These are BLOCKED unconditionally.
BLACKLISTED_JURISDICTIONS: FrozenSet[str] = frozenset({
    "IR",  # Iran
    "KP",  # North Korea (DPRK)
    "SY",  # Syria
    "CU",  # Cuba
})

# Additional high-risk jurisdictions requiring enhanced screening
HIGH_RISK_JURISDICTIONS: FrozenSet[str] = frozenset({
    "AF",  # Afghanistan
    "BY",  # Belarus
    "MM",  # Myanmar
    "RU",  # Russia
    "VE",  # Venezuela
    "YE",  # Yemen
    "ZW",  # Zimbabwe
})


class SanctionsListSource(Enum):
    """Known sanctions list sources."""

    OFAC_SDN = "ofac_sdn"              # US OFAC Specially Designated Nationals
    OFAC_CONSOLIDATED = "ofac_consolidated"
    EU_CONSOLIDATED = "eu_consolidated"
    UN_CONSOLIDATED = "un_consolidated"
    UK_OFSI = "uk_ofsi"               # UK Office of Financial Sanctions
    CUSTOM = "custom"


class ScreeningResult(Enum):
    CLEAR = "clear"
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    BLACKLISTED_JURISDICTION = "blacklisted_jurisdiction"
    HIGH_RISK_JURISDICTION = "high_risk_jurisdiction"
    STALE_DATA = "stale_data"


class RiskLevel(Enum):
    BLOCK = "block"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CLEAR = "clear"


# ======================================================================
# Data Models
# ======================================================================

@dataclass(frozen=True)
class SanctionsListMetadata:
    """Metadata for a loaded sanctions list — no raw data stored."""

    source: SanctionsListSource
    entry_count: int
    loaded_at: float
    list_hash: str          # SHA-256 of the full list for integrity

    @property
    def age_seconds(self) -> float:
        return time.time() - self.loaded_at

    @property
    def is_stale(self) -> bool:
        return self.age_seconds > MAX_STALENESS_SECONDS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value,
            "entry_count": self.entry_count,
            "loaded_at": self.loaded_at,
            "list_hash": self.list_hash,
            "age_seconds": self.age_seconds,
            "is_stale": self.is_stale,
        }


@dataclass(frozen=True)
class ScreeningReport:
    """Result of screening an entity or jurisdiction."""

    entity_hash: str
    result: ScreeningResult
    risk_level: RiskLevel
    matched_sources: frozenset       # set of SanctionsListSource values
    detail: str
    evidence_hash: str = ""
    screened_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_hash": self.entity_hash,
            "result": self.result.value,
            "risk_level": self.risk_level.value,
            "matched_sources": sorted(s.value if isinstance(s, SanctionsListSource) else s
                                       for s in self.matched_sources),
            "detail": self.detail,
            "evidence_hash": self.evidence_hash,
            "screened_at": self.screened_at,
        }


# ======================================================================
# Global Sanctions Screening Engine
# ======================================================================

class GlobalSanctionsEngine:
    """Hash-based global sanctions screening engine.

    All entity identifiers are stored and compared as SHA-256 hashes.
    No raw PII or sanctions list data is ever retained.
    Fail-closed: stale data or missing lists → BLOCK.
    """

    def __init__(self) -> None:
        # source → set of entity hashes
        self._lists: Dict[SanctionsListSource, Set[str]] = {}
        # source → metadata
        self._metadata: Dict[SanctionsListSource, SanctionsListMetadata] = {}

    # ------------------------------------------------------------------
    # List Management
    # ------------------------------------------------------------------

    def load_list(
        self,
        source: SanctionsListSource,
        entity_hashes: Set[str],
    ) -> SanctionsListMetadata:
        """Load a pre-hashed sanctions list.

        Callers are responsible for hashing entity identifiers before
        passing them here — this engine **never** sees raw data.
        """
        self._lists[source] = set(entity_hashes)

        # Compute integrity hash over sorted entries
        sorted_hashes = sorted(entity_hashes)
        list_payload = ":".join(sorted_hashes)
        list_hash = hashlib.sha256(list_payload.encode()).hexdigest()

        meta = SanctionsListMetadata(
            source=source,
            entry_count=len(entity_hashes),
            loaded_at=time.time(),
            list_hash=list_hash,
        )
        self._metadata[source] = meta
        return meta

    def get_list_metadata(
        self, source: SanctionsListSource,
    ) -> Optional[SanctionsListMetadata]:
        return self._metadata.get(source)

    def check_staleness(self) -> Dict[SanctionsListSource, bool]:
        """Return staleness status for all loaded lists."""
        return {
            source: meta.is_stale
            for source, meta in self._metadata.items()
        }

    def has_stale_lists(self) -> bool:
        """Return True if any loaded list exceeds 24 h staleness."""
        return any(meta.is_stale for meta in self._metadata.values())

    # ------------------------------------------------------------------
    # Entity Screening
    # ------------------------------------------------------------------

    @staticmethod
    def hash_entity(identifier: str) -> str:
        """Normalise and SHA-256-hash an entity identifier."""
        return hashlib.sha256(
            identifier.strip().lower().encode("utf-8")
        ).hexdigest()

    def screen_entity(self, identifier: str) -> ScreeningReport:
        """Screen an entity identifier against all loaded sanctions lists.

        Fail-closed:
          - If no lists are loaded → BLOCK (cannot verify clearance).
          - If any list is stale → BLOCK with STALE_DATA.
          - If entity hash is found → BLOCK (MATCH).
        """
        entity_hash = self.hash_entity(identifier)

        # Fail-closed: no lists loaded
        if not self._lists:
            return ScreeningReport(
                entity_hash=entity_hash,
                result=ScreeningResult.STALE_DATA,
                risk_level=RiskLevel.BLOCK,
                matched_sources=frozenset(),
                detail="No sanctions lists loaded — fail-closed.",
                evidence_hash=self._evidence(entity_hash, "no_lists"),
            )

        # Fail-closed: stale data
        if self.has_stale_lists():
            stale_sources = [
                s for s, meta in self._metadata.items() if meta.is_stale
            ]
            return ScreeningReport(
                entity_hash=entity_hash,
                result=ScreeningResult.STALE_DATA,
                risk_level=RiskLevel.BLOCK,
                matched_sources=frozenset(stale_sources),
                detail=f"Stale sanctions data ({len(stale_sources)} list(s) exceed 24 h).",
                evidence_hash=self._evidence(entity_hash, "stale"),
            )

        # Check entity against all lists
        matched: Set[SanctionsListSource] = set()
        for source, hashes in self._lists.items():
            if entity_hash in hashes:
                matched.add(source)

        if matched:
            return ScreeningReport(
                entity_hash=entity_hash,
                result=ScreeningResult.MATCH,
                risk_level=RiskLevel.BLOCK,
                matched_sources=frozenset(matched),
                detail=f"Entity hash matched {len(matched)} sanctions list(s).",
                evidence_hash=self._evidence(entity_hash, "match"),
            )

        return ScreeningReport(
            entity_hash=entity_hash,
            result=ScreeningResult.CLEAR,
            risk_level=RiskLevel.CLEAR,
            matched_sources=frozenset(),
            detail="No sanctions match.",
            evidence_hash=self._evidence(entity_hash, "clear"),
        )

    # ------------------------------------------------------------------
    # Jurisdiction Screening
    # ------------------------------------------------------------------

    def screen_jurisdiction(self, country_code: str) -> ScreeningReport:
        """Screen a jurisdiction (ISO 3166-1 alpha-2) against blacklists.

        Fail-closed: blacklisted jurisdictions are always BLOCK.
        """
        code = country_code.strip().upper()
        entity_hash = hashlib.sha256(code.encode()).hexdigest()

        if code in BLACKLISTED_JURISDICTIONS:
            return ScreeningReport(
                entity_hash=entity_hash,
                result=ScreeningResult.BLACKLISTED_JURISDICTION,
                risk_level=RiskLevel.BLOCK,
                matched_sources=frozenset(),
                detail=f"Jurisdiction {code} is blacklisted (comprehensive sanctions).",
                evidence_hash=self._evidence(entity_hash, "blacklisted"),
            )

        if code in HIGH_RISK_JURISDICTIONS:
            return ScreeningReport(
                entity_hash=entity_hash,
                result=ScreeningResult.HIGH_RISK_JURISDICTION,
                risk_level=RiskLevel.HIGH,
                matched_sources=frozenset(),
                detail=f"Jurisdiction {code} is high-risk — enhanced screening required.",
                evidence_hash=self._evidence(entity_hash, "high_risk"),
            )

        return ScreeningReport(
            entity_hash=entity_hash,
            result=ScreeningResult.CLEAR,
            risk_level=RiskLevel.CLEAR,
            matched_sources=frozenset(),
            detail=f"Jurisdiction {code} is not sanctioned.",
            evidence_hash=self._evidence(entity_hash, "clear"),
        )

    # ------------------------------------------------------------------
    # Combined Screening
    # ------------------------------------------------------------------

    def full_screening(
        self,
        identifier: str,
        country_code: str,
    ) -> List[ScreeningReport]:
        """Run entity + jurisdiction screening. Returns list of reports."""
        return [
            self.screen_entity(identifier),
            self.screen_jurisdiction(country_code),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _evidence(entity_hash: str, context: str) -> str:
        payload = f"{entity_hash}:{context}:{time.time()}"
        return hashlib.sha256(payload.encode()).hexdigest()
