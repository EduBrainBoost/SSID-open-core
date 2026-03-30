# ======================================================================
# GENERATED FILE — DO NOT EDIT MANUALLY
#
# GENERATED_BY=SSID-EMS
# EMS_COMMIT=unknown
# GENERATED_AT=2026-03-02T05:44:34Z
# PATTERN_SET_SHA256=47989d263e74d00d6e0908fd1ac7d0ae1134708938422797f3167bbc5a64cfcd
#
# Source of Truth: SSID-EMS/src/ssidctl/core/secret_patterns.py
# To update: ssidctl export-secret-patterns --target-ssid <path>
# ======================================================================
"""Secret pattern definitions — generated from SSID-EMS.

All secret-detection logic in SSID (redaction_filter, data_minimization)
MUST import from this module. No pattern duplication elsewhere.
"""
from __future__ import annotations

import re
from typing import Any

PATTERN_SET_SHA256 = "47989d263e74d00d6e0908fd1ac7d0ae1134708938422797f3167bbc5a64cfcd"

PATTERNS: list[dict[str, Any]] = [
    {
        "id": 'SEC-AWS-001',
        "name": 'aws_access_key',
        "regex": '(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}',
        "replacement": '<AWS_KEY_REDACTED>',
    },
    {
        "id": 'SEC-GH-001',
        "name": 'github_token',
        "regex": '(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9_]{36,}',
        "replacement": '<GITHUB_TOKEN_REDACTED>',
    },
    {
        "id": 'SEC-GH-002',
        "name": 'github_pat',
        "regex": 'github_pat_[A-Za-z0-9_]{22,}',
        "replacement": '<GITHUB_PAT_REDACTED>',
    },
    {
        "id": 'SEC-GL-001',
        "name": 'gitlab_pat',
        "regex": 'glpat-[A-Za-z0-9\\-_]{20,}',
        "replacement": '<GITLAB_PAT_REDACTED>',
    },
    {
        "id": 'SEC-SLACK-001',
        "name": 'slack_token',
        "regex": 'xox[baprs]-[A-Za-z0-9\\-]{10,}',
        "replacement": '<SLACK_TOKEN_REDACTED>',
    },
    {
        "id": 'SEC-STRIPE-001',
        "name": 'stripe_key',
        "regex": '[sr]k_(?:live|test)_[A-Za-z0-9]{10,}',
        "replacement": '<STRIPE_KEY_REDACTED>',
    },
    {
        "id": 'SEC-PK-001',
        "name": 'private_key_header',
        "regex": '-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----',
        "replacement": '<PRIVATE_KEY_REDACTED>',
    },
    {
        "id": 'SEC-API-001',
        "name": 'generic_api_key',
        "regex": '(?i)(?:(?:sk-|pk-)[A-Za-z0-9_\\-]{20,}|bearer\\s+[A-Za-z0-9_\\-]{20,}|api[_-]?key\\s*[=:]\\s*[\'\\"]?[A-Za-z0-9_\\-]{20,})',
        "replacement": '<API_KEY_REDACTED>',
    },
    {
        "id": 'SEC-HEX-001',
        "name": 'long_hex_token',
        "regex": '(?<!sha256:)(?<!sha384:)(?<!sha512:)(?<!sha1:)(?<!commit )(?<!merkle:)(?<!digest:)(?<!integrity:)(?<!checksum:)\\b[0-9a-fA-F]{40,}\\b',
        "replacement": '<HEX_REDACTED>',
    },
]

# Pre-compiled patterns (module-level, no per-call compilation)
COMPILED: list[tuple[str, re.Pattern[str], str]] = [
    (p["id"], re.compile(p["regex"]), p["replacement"])
    for p in PATTERNS
]


def find(text: str) -> list[str]:
    """Return list of pattern IDs that match in text.

    Does NOT return the matched token itself (data-minimization).
    """
    return [
        pattern_id
        for pattern_id, regex, _replacement in COMPILED
        if regex.search(text)
    ]


def redact(text: str) -> tuple[str, int]:
    """Redact all secret patterns in text.

    Returns (redacted_text, redaction_count).
    Replaces entire match — no partial fragments remain.
    """
    count = 0
    result = text
    for _pattern_id, regex, replacement in COMPILED:
        result, n = regex.subn(replacement, result)
        count += n
    return result, count
