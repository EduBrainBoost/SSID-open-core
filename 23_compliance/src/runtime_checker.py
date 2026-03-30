"""23_compliance — Compliance runtime checks.

SAFE-FIX: Fail-closed on any detection. Hash-only, no raw PII stored.
Pattern-based PII detection with automatic redaction.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class Severity(Enum):
    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True)
class ComplianceFinding:
    """Single compliance finding — never contains raw PII."""

    severity: Severity
    category: str  # sanctions | pii | secret
    detail: str  # redacted human-readable detail
    evidence_hash: str = ""  # SHA-256 of the raw evidence
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "severity": self.severity.value,
            "category": self.category,
            "detail": self.detail,
            "evidence_hash": self.evidence_hash,
            "timestamp": self.timestamp,
        }
        return d


# ======================================================================
# Sanctions Screener (hash-based, no raw PII)
# ======================================================================

class SanctionsScreener:
    """Hash-based sanctions screening.

    The screener stores only SHA-256 hashes of sanctioned entity
    identifiers.  Lookups are performed by hashing the query and
    comparing against the set — **no raw PII is ever stored or logged**.
    """

    def __init__(self, sanctioned_hashes: Optional[Set[str]] = None) -> None:
        self._hashes: Set[str] = set(sanctioned_hashes or [])

    @staticmethod
    def hash_entity(identifier: str) -> str:
        """Normalise and hash an entity identifier."""
        normalised = identifier.strip().lower()
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()

    def add_hash(self, identifier_hash: str) -> None:
        """Add a pre-computed hash to the sanctions set."""
        self._hashes.add(identifier_hash)

    def add_entity(self, identifier: str) -> None:
        """Hash an identifier and add it to the sanctions set."""
        self._hashes.add(self.hash_entity(identifier))

    def screen(self, identifier: str) -> ComplianceFinding:
        """Screen *identifier* against the sanctions set.

        Fail-closed: any match → BLOCK.
        """
        h = self.hash_entity(identifier)
        if h in self._hashes:
            return ComplianceFinding(
                severity=Severity.BLOCK,
                category="sanctions",
                detail="Entity hash matched sanctions list.",
                evidence_hash=h,
            )
        return ComplianceFinding(
            severity=Severity.INFO,
            category="sanctions",
            detail="No sanctions match.",
            evidence_hash=h,
        )


# ======================================================================
# PII Detector (pattern-based, redaction)
# ======================================================================

# Patterns intentionally kept simple; real deployments should use
# validated libraries.  Order matters: more specific first.
_PII_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "email",
        "regex": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    },
    {
        "name": "phone",
        "regex": re.compile(r"\+?\d[\d\-\s]{7,}\d"),
    },
    {
        "name": "ssn",
        "regex": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    },
    {
        "name": "credit_card",
        "regex": re.compile(r"\b(?:\d[ \-]*?){13,19}\b"),
    },
]


class PIIDetector:
    """Pattern-based PII detector with automatic redaction.

    Detected PII is **never** stored in raw form — only its SHA-256
    hash and the pattern name are recorded.
    """

    def __init__(
        self,
        extra_patterns: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._patterns = list(_PII_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

    def scan(self, text: str) -> List[ComplianceFinding]:
        """Scan *text* for PII patterns.  Returns one finding per match."""
        findings: List[ComplianceFinding] = []
        for pat in self._patterns:
            for match in pat["regex"].finditer(text):
                raw = match.group(0)
                h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                findings.append(
                    ComplianceFinding(
                        severity=Severity.BLOCK,
                        category="pii",
                        detail=f"PII detected: type={pat['name']} (redacted).",
                        evidence_hash=h,
                    )
                )
        return findings

    def redact(self, text: str) -> str:
        """Return *text* with all detected PII replaced by ``[REDACTED]``."""
        result = text
        for pat in self._patterns:
            result = pat["regex"].sub("[REDACTED]", result)
        return result


# ======================================================================
# Secret Scanner
# ======================================================================

_SECRET_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "aws_key",
        "regex": re.compile(r"AKIA[0-9A-Z]{16}"),
    },
    {
        "name": "generic_secret",
        "regex": re.compile(
            r"(?i)(?:password|secret|token|api_key|apikey)\s*[:=]\s*\S+",
        ),
    },
    {
        "name": "private_key_header",
        "regex": re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    },
]


class SecretScanner:
    """Detect hardcoded secrets in text. Fail-closed on detection."""

    def __init__(self) -> None:
        self._patterns = list(_SECRET_PATTERNS)

    def scan(self, text: str) -> List[ComplianceFinding]:
        findings: List[ComplianceFinding] = []
        for pat in self._patterns:
            for match in pat["regex"].finditer(text):
                raw = match.group(0)
                h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                findings.append(
                    ComplianceFinding(
                        severity=Severity.BLOCK,
                        category="secret",
                        detail=f"Secret detected: type={pat['name']} (redacted).",
                        evidence_hash=h,
                    )
                )
        return findings


# ======================================================================
# Unified Compliance Checker
# ======================================================================

class ComplianceChecker:
    """Unified runtime compliance checker.

    Aggregates sanctions screening, PII detection, and secret scanning.
    Fail-closed: if **any** scanner returns BLOCK the overall result
    is BLOCK.
    """

    def __init__(
        self,
        sanctions_screener: Optional[SanctionsScreener] = None,
        pii_detector: Optional[PIIDetector] = None,
        secret_scanner: Optional[SecretScanner] = None,
    ) -> None:
        self.sanctions = sanctions_screener or SanctionsScreener()
        self.pii = pii_detector or PIIDetector()
        self.secrets = secret_scanner or SecretScanner()

    def check_entity(self, identifier: str) -> List[ComplianceFinding]:
        """Screen a single entity identifier (sanctions only)."""
        return [self.sanctions.screen(identifier)]

    def check_text(self, text: str) -> List[ComplianceFinding]:
        """Scan free-text for PII and secrets."""
        findings: List[ComplianceFinding] = []
        findings.extend(self.pii.scan(text))
        findings.extend(self.secrets.scan(text))
        return findings

    def check_all(
        self,
        identifier: str,
        text: str,
    ) -> List[ComplianceFinding]:
        """Run all checks and return combined findings."""
        findings: List[ComplianceFinding] = []
        findings.extend(self.check_entity(identifier))
        findings.extend(self.check_text(text))
        return findings

    def has_block(self, findings: List[ComplianceFinding]) -> bool:
        """Return ``True`` if any finding is BLOCK severity."""
        return any(f.severity is Severity.BLOCK for f in findings)
