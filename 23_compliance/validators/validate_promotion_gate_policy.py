"""Validator: promotion_gate_policy
Source policy: 23_compliance/policies/registry/promotion_gate_policy.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""
from typing import Any, Dict, List, Tuple


def validate_promotion_gate_policy(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates data against promotion_gate_policy.
    Derived from: 23_compliance/policies/registry/promotion_gate_policy.rego

    Returns (True, []) if all promotion gate checks pass,
    otherwise (False, [violations]).
    """
    violations: List[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    canonical_artifacts: List[Dict] = data.get("canonical_artifacts", [])
    derivative_artifacts: List[Dict] = data.get("derivative_artifacts", [])
    export_scopes: List[str] = data.get("export_scopes", [])
    forbidden_patterns: List[str] = data.get("forbidden_patterns", [])

    derivative_paths = {d.get("path") for d in derivative_artifacts if isinstance(d, dict)}
    canonical_paths = {c.get("path") for c in canonical_artifacts if isinstance(c, dict)}

    # PROMO_ENFORCE_001: canonical on_disk but no derivative counterpart
    for c in canonical_artifacts:
        if isinstance(c, dict) and c.get("on_disk") is True:
            if c.get("path") not in derivative_paths:
                violations.append(
                    f"PROMO_ENFORCE_001: canonical '{c.get('path')}' on_disk but no derivative counterpart"
                )

    # PROMO_ENFORCE_002: derivative with no canonical source
    for d in derivative_artifacts:
        if isinstance(d, dict):
            if d.get("path") not in canonical_paths:
                violations.append(
                    f"PROMO_ENFORCE_002: derivative '{d.get('path')}' has no canonical source"
                )

    # PROMO_ENFORCE_003: derivative matches forbidden pattern
    for d in derivative_artifacts:
        if isinstance(d, dict):
            for pattern in forbidden_patterns:
                if pattern in (d.get("path") or ""):
                    violations.append(
                        f"PROMO_ENFORCE_003: derivative '{d.get('path')}' matches forbidden pattern '{pattern}'"
                    )

    # PROMO_ENFORCE_004: hash drift
    canonical_by_path = {c["path"]: c for c in canonical_artifacts if isinstance(c, dict) and c.get("path")}
    for d in derivative_artifacts:
        if isinstance(d, dict) and d.get("path") in canonical_by_path:
            c = canonical_by_path[d["path"]]
            if c.get("hash_sha256") and d.get("hash_sha256"):
                if c["hash_sha256"] != d["hash_sha256"]:
                    violations.append(
                        f"PROMO_ENFORCE_004: hash drift for '{d.get('path')}'"
                    )

    # PROMO_ENFORCE_005: export scope violation
    for d in derivative_artifacts:
        if isinstance(d, dict):
            path = d.get("path") or ""
            if not any(path.startswith(scope) for scope in export_scopes):
                violations.append(
                    f"PROMO_ENFORCE_005: derivative '{path}' outside allowed export scopes"
                )

    return (len(violations) == 0, violations)
