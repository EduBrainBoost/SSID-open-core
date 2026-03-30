"""Validator: sot_convergence_policy
Source policy: 23_compliance/policies/sot/sot_convergence_policy.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""
from typing import Any, Dict, List, Tuple


def validate_sot_convergence_policy(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates data against sot_convergence_policy.
    Derived from: 23_compliance/policies/sot/sot_convergence_policy.rego

    Returns (True, []) if no deny conditions fire (convergence is compliant),
    otherwise (False, [violations]).
    """
    violations: List[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    # D-001: overall status FAIL
    if data.get("status") == "FAIL":
        violations.append("D-001: overall convergence status is FAIL")

    # D-002: canonical repo with missing artifacts
    if data.get("repo_role") == "canonical":
        missing = data.get("missing_artifacts", [])
        if len(missing) > 0:
            violations.append(
                f"D-002: canonical repo missing {len(missing)} artifact(s): {', '.join(str(m) for m in missing[:5])}"
            )

    drift_findings: List[Dict] = data.get("drift_findings", [])

    for finding in drift_findings:
        if not isinstance(finding, dict):
            continue
        # D-003: protected_scope_attempt
        if finding.get("class") == "protected_scope_attempt":
            violations.append(
                f"D-003: protected_scope_attempt in '{finding.get('path', '<unknown>')}'"
            )
        # D-004: critical severity
        if finding.get("severity") == "critical":
            violations.append(
                f"D-004: critical drift finding in '{finding.get('path', '<unknown>')}': {finding.get('class', 'unknown')}"
            )

    return (len(violations) == 0, violations)
