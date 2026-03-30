"""MiCA Marketing Linter — scans text for non-compliant marketing claims.

Returns a list of findings as dicts with keys: kind, term, severity, span.
"""

from __future__ import annotations

import re
from typing import Any


# Prohibited terms per MiCA Article 53 / Annex VI guidance
_PROHIBITED_PATTERNS: list[tuple[str, str, str]] = [
    (r"\bguaranteed\s+returns?\b", "guaranteed_return", "HIGH"),
    (r"\brisk[- ]?free\b", "risk_free_claim", "HIGH"),
    (r"\binvestment\b", "investment_language", "MEDIUM"),
    (r"\bprofit\b", "profit_claim", "MEDIUM"),
    (r"\byield\b", "yield_claim", "MEDIUM"),
    (r"\bdividend\b", "dividend_claim", "HIGH"),
    (r"\bpassive\s+income\b", "passive_income", "HIGH"),
    (r"\bapy\b", "apy_claim", "HIGH"),
    (r"\bapr\b", "apr_claim", "HIGH"),
    (r"\bstaking\s+reward\b", "staking_reward", "MEDIUM"),
]


def scan_text(text: str) -> list[dict[str, Any]]:
    """Scan text for MiCA-non-compliant marketing terms.

    Returns list of dicts with keys: kind, term, severity, span.
    """
    findings: list[dict[str, Any]] = []
    text_lower = text.lower()
    for pattern, kind, severity in _PROHIBITED_PATTERNS:
        for match in re.finditer(pattern, text_lower):
            findings.append({
                "kind": kind,
                "term": match.group(),
                "severity": severity,
                "span": (match.start(), match.end()),
            })
    return findings


def scan_file(path: str) -> list[dict[str, Any]]:
    """Scan a file for MiCA-non-compliant marketing terms."""
    with open(path, "r", encoding="utf-8") as f:
        return scan_text(f.read())


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: mica_marketing_linter.py <file>")
        sys.exit(1)

    findings = scan_file(sys.argv[1])
    if findings:
        print(f"FAIL: {len(findings)} MiCA marketing violations found")
        for f in findings:
            print(f"  [{f['severity']}] {f['kind']}: '{f['term']}' at {f['span']}")
        sys.exit(1)
    else:
        print("PASS: No MiCA marketing violations found")
        sys.exit(0)
