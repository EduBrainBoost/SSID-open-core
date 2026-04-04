"""Validator: interfederation_claims_guard
Source policy: 23_compliance/policies/interfederation/interfederation_claims_guard.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""

import re
from typing import Any

FORBIDDEN_CLAIMS = [
    "interfederation active",
    "interfederation certified",
    "mutual validation complete",
    "bidirectional verification achieved",
    "co-truth protocol active",
    "proof nexus certified",
    "cross-system verified",
]

SCORE_PATTERN = re.compile(r"\d+[%/]\d*\s*(interfed|mutual|co-truth)", re.IGNORECASE)


def _proof_exists(data: dict[str, Any]) -> bool:
    snapshot = data.get("proof_snapshot")
    if not snapshot or not isinstance(snapshot, dict):
        return False
    return (
        bool(snapshot.get("ssid_commit"))
        and bool(snapshot.get("opencore_commit"))
        and len(snapshot.get("file_hashes", {})) > 0
    )


def validate_interfederation_claims_guard(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validates data against interfederation_claims_guard policy.
    Derived from: 23_compliance/policies/interfederation/interfederation_claims_guard.rego

    Returns (True, []) if no forbidden interfederation claims or numeric scores found
    without a valid proof snapshot, otherwise (False, [violations]).
    """
    violations: list[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    documents: list[dict] = data.get("documents", [])
    proof_present = _proof_exists(data)

    for doc in documents:
        if not isinstance(doc, dict):
            continue
        content_lower = doc.get("content", "").lower()
        doc_id = doc.get("path", "<unknown>")

        if not proof_present:
            for claim in FORBIDDEN_CLAIMS:
                if claim in content_lower:
                    violations.append(f"Forbidden interfederation claim '{claim}' in '{doc_id}' without proof snapshot")

        if SCORE_PATTERN.search(content_lower):
            violations.append(f"Numeric interfederation score pattern found in '{doc_id}'")

    return (len(violations) == 0, violations)
