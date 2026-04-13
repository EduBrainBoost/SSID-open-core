"""Validator: claims_guard
Source policy: 23_compliance/policies/claims_guard.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""

from typing import Any

FORBIDDEN_CLAIMS = [
    "INTERFEDERATION_ACTIVE",
    "INTERFEDERATION_CERTIFIED",
    "EXECUTION_READY",
    "PERFECT CERTIFIED",
    "MUTUAL_VALIDATION_COMPLETE",
    "BIDIRECTIONAL_VERIFICATION_ACHIEVED",
    "CO_TRUTH_PROTOCOL_ACTIVE",
    "PROOF_NEXUS_CERTIFIED",
    "CROSS_SYSTEM_VERIFIED",
    "META_CONTINUUM_READY",
]


def validate_claims_guard(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validates data against claims_guard policy.
    Derived from: 23_compliance/policies/claims_guard.rego

    Returns (True, []) if no forbidden claims are present without evidence,
    otherwise (False, [list of violation descriptions]).
    """
    violations: list[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    scanned_files: list[dict] = data.get("scanned_files", [])
    evidence_flags: list[dict] = data.get("evidence_flags", [])

    verified_claims = {
        flag["claim"] for flag in evidence_flags if isinstance(flag, dict) and flag.get("verified") is True
    }

    for file_entry in scanned_files:
        if not isinstance(file_entry, dict):
            continue
        content = file_entry.get("content", "")
        file_path = file_entry.get("path", "<unknown>")
        for claim in FORBIDDEN_CLAIMS:
            if claim in content and claim not in verified_claims:
                violations.append(f"Forbidden claim '{claim}' found in '{file_path}' without verified evidence")

    return (len(violations) == 0, violations)
