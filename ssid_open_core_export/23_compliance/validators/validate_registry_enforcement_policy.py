"""Validator: registry_enforcement_policy
Source policy: 23_compliance/policies/registry/registry_enforcement_policy.rego
Phase 3 stub — A02_A03_COMPLETION
Phase 2 Tuple-Fix — AGENT_A9_TEST_EVIDENCE
"""

from typing import Any

SOT_PATH_PREFIXES = (
    "03_core/validators/sot/",
    "23_compliance/policies/sot/",
    "16_codex/contracts/sot/",
    "12_tooling/cli/sot_",
    "11_test_simulation/tests_compliance/test_sot_",
)


def _is_sot_artifact(artifact: dict) -> bool:
    path = artifact.get("path") or ""
    return any(path.startswith(prefix) for prefix in SOT_PATH_PREFIXES)


def validate_registry_enforcement_policy(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validates data against registry_enforcement_policy.
    Derived from: 23_compliance/policies/registry/registry_enforcement_policy.rego

    Returns (True, []) if all registry enforcement checks pass,
    otherwise (False, [violations]).
    """
    violations: list[str] = []

    if not isinstance(data, dict):
        return (False, ["Input data is not a dict"])

    artifacts: list[dict] = data.get("artifacts", [])
    guards: list[dict] = data.get("guards", [])

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue

        path = artifact.get("path", "<unknown>")

        # REGISTRY_ENFORCE_001: on_disk without hash
        if artifact.get("on_disk") is True and not artifact.get("hash_sha256"):
            violations.append(f"REGISTRY_ENFORCE_001: artifact '{path}' on_disk without hash_sha256")

        # REGISTRY_ENFORCE_002: hash drift
        if (artifact.get("on_disk") is True and artifact.get("hash_sha256") and artifact.get("disk_hash")) and artifact[
            "hash_sha256"
        ] != artifact["disk_hash"]:
            violations.append(f"REGISTRY_ENFORCE_002: hash drift for '{path}'")

        # REGISTRY_ENFORCE_003: missing or empty evidence_ref
        if not artifact.get("evidence_ref"):
            violations.append(f"REGISTRY_ENFORCE_003: missing evidence_ref for '{path}'")

        # REGISTRY_ENFORCE_004: SoT artifact without source_of_truth_ref
        if _is_sot_artifact(artifact) and not artifact.get("source_of_truth_ref"):
            violations.append(f"REGISTRY_ENFORCE_004: SoT artifact '{path}' without source_of_truth_ref")

    # REGISTRY_ENFORCE_005: fail-open guards
    for guard in guards:
        if not isinstance(guard, dict):
            continue
        if guard.get("unknown_value_behavior") != "fail":
            violations.append(f"REGISTRY_ENFORCE_005: guard '{guard.get('name', '<unknown>')}' has fail-open behavior")

    return (len(violations) == 0, violations)
