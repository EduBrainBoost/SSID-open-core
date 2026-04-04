"""Validator: sot_policy
Source policy: 23_compliance/policies/sot/sot_policy.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""

from typing import Any


def validate_sot_policy(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validates data against sot_policy (v4.1 Full Enforcement).
    Derived from: 23_compliance/policies/sot/sot_policy.rego

    Returns (True, []) if ROOT-24-LOCK context present and no write gate violations,
    otherwise (False, [violations]).
    """
    violations: list[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    # ROOT-24-LOCK required
    if data.get("security_context") != "ROOT-24-LOCK":
        violations.append(f"security_context is '{data.get('security_context')}', expected 'ROOT-24-LOCK'")

    # Write gate: allowed_paths must be populated for validation
    changed_files: list[dict] = data.get("changed_files", [])
    allowed_paths: list[str] = data.get("allowed_paths", [])

    if changed_files and allowed_paths:
        for f in changed_files:
            if not isinstance(f, dict):
                continue
            path = f.get("path") or ""
            if not any(path.startswith(ap) for ap in allowed_paths):
                violations.append(f"Write gate violation: '{path}' not in allowed_paths")

    return (len(violations) == 0, violations)
