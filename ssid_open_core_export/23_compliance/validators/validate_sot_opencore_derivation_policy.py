"""Validator: sot_opencore_derivation_policy
Source policy: 23_compliance/policies/sot/sot_opencore_derivation_policy.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""

from typing import Any

DENY_FINDING_CLASSES = {
    "forbidden_export",
    "contract_hash_mismatch",
    "export_scope_violation",
}


def validate_sot_opencore_derivation_policy(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validates data against sot_opencore_derivation_policy.
    Derived from: 23_compliance/policies/sot/sot_opencore_derivation_policy.rego

    Returns (True, []) if no deny conditions fire,
    otherwise (False, [violations]).
    """
    violations: list[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    # D-005: overall status fail
    if data.get("status") == "fail":
        violations.append("D-005: overall derivation status is 'fail'")

    findings: list[dict] = data.get("findings", [])

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        cls = finding.get("class")
        path = finding.get("path", "<unknown>")

        # D-001, D-002, D-004
        if cls in DENY_FINDING_CLASSES:
            violations.append(f"Deny finding class '{cls}' in '{path}'")

        # D-003: critical stale_derivative_binding
        if cls == "stale_derivative_binding" and finding.get("severity") == "critical":
            violations.append(f"D-003: critical stale_derivative_binding in '{path}'")

    return (len(violations) == 0, violations)
