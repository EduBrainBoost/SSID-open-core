"""Validator: proposal_validator
Validates governance proposal schemas (YAML registry, JSON ballots).
Enforces required fields, quorum rules, and threshold rules.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# --- Required fields ---

REGISTRY_PROPOSAL_REQUIRED_FIELDS = [
    "id",
    "title",
    "type",
    "status",
    "author",
    "created_at",
    "ballot_ref",
    "quorum_required",
    "threshold_required",
]

BALLOT_REQUIRED_FIELDS = [
    "proposal_id",
    "title",
    "type",
    "status",
    "quorum",
    "threshold",
    "voting",
    "evidence_hash",
]

VALID_STATUSES = {"draft", "active", "passed", "rejected", "enacted", "cancelled"}

VALID_TYPES = {"parameter_change", "protocol_upgrade", "treasury_allocation", "governance_rule"}


def validate_registry(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a proposal registry YAML structure.

    Returns (True, []) if valid, otherwise (False, [violations]).
    """
    violations: List[str] = []

    if not isinstance(data, dict):
        return (False, ["Registry data is not a dict"])

    if "proposals" not in data:
        violations.append("Missing top-level 'proposals' key")
        return (False, violations)

    proposals = data["proposals"]
    if not isinstance(proposals, list):
        violations.append("'proposals' must be a list")
        return (False, violations)

    for i, prop in enumerate(proposals):
        if not isinstance(prop, dict):
            violations.append(f"proposals[{i}]: entry is not a dict")
            continue

        for field in REGISTRY_PROPOSAL_REQUIRED_FIELDS:
            if field not in prop:
                violations.append(f"proposals[{i}]: missing required field '{field}'")

        status = prop.get("status")
        if status and status not in VALID_STATUSES:
            violations.append(
                f"proposals[{i}]: invalid status '{status}', "
                f"expected one of {sorted(VALID_STATUSES)}"
            )

        ptype = prop.get("type")
        if ptype and ptype not in VALID_TYPES:
            violations.append(
                f"proposals[{i}]: invalid type '{ptype}', "
                f"expected one of {sorted(VALID_TYPES)}"
            )

        quorum = prop.get("quorum_required")
        if quorum is not None:
            if not isinstance(quorum, (int, float)) or not (0.0 < quorum <= 1.0):
                violations.append(
                    f"proposals[{i}]: quorum_required must be a float in (0.0, 1.0]"
                )

        threshold = prop.get("threshold_required")
        if threshold is not None:
            if not isinstance(threshold, (int, float)) or not (0.0 < threshold <= 1.0):
                violations.append(
                    f"proposals[{i}]: threshold_required must be a float in (0.0, 1.0]"
                )

    return (len(violations) == 0, violations)


def validate_ballot(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a ballot record JSON structure.

    Returns (True, []) if valid, otherwise (False, [violations]).
    """
    violations: List[str] = []

    if not isinstance(data, dict):
        return (False, ["Ballot data is not a dict"])

    for field in BALLOT_REQUIRED_FIELDS:
        if field not in data:
            violations.append(f"Missing required field '{field}'")

    status = data.get("status")
    if status and status not in VALID_STATUSES:
        violations.append(
            f"Invalid status '{status}', expected one of {sorted(VALID_STATUSES)}"
        )

    btype = data.get("type")
    if btype and btype not in VALID_TYPES:
        violations.append(
            f"Invalid type '{btype}', expected one of {sorted(VALID_TYPES)}"
        )

    # Quorum validation
    quorum = data.get("quorum")
    if isinstance(quorum, dict):
        required = quorum.get("required")
        achieved = quorum.get("achieved")
        if required is not None and achieved is not None:
            if isinstance(required, (int, float)) and isinstance(achieved, (int, float)):
                expected_met = achieved >= required
                actual_met = quorum.get("quorum_met")
                if actual_met is not None and actual_met != expected_met:
                    violations.append(
                        f"quorum_met is {actual_met} but achieved ({achieved}) "
                        f"vs required ({required}) implies {expected_met}"
                    )

    # Threshold validation
    threshold = data.get("threshold")
    if isinstance(threshold, dict):
        required = threshold.get("required")
        achieved = threshold.get("achieved")
        if required is not None and achieved is not None:
            if isinstance(required, (int, float)) and isinstance(achieved, (int, float)):
                expected_met = achieved >= required
                actual_met = threshold.get("threshold_met")
                if actual_met is not None and actual_met != expected_met:
                    violations.append(
                        f"threshold_met is {actual_met} but achieved ({achieved}) "
                        f"vs required ({required}) implies {expected_met}"
                    )

    # Evidence hash format
    evidence_hash = data.get("evidence_hash")
    if evidence_hash is not None:
        if not isinstance(evidence_hash, str) or not evidence_hash.startswith("sha3-256:"):
            violations.append(
                "evidence_hash must be a string starting with 'sha3-256:'"
            )

    return (len(violations) == 0, violations)


def validate_ballot_file(path: str) -> Tuple[bool, List[str]]:
    """Load and validate a ballot JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return (False, [f"Failed to load ballot file: {e}"])
    return validate_ballot(data)


def validate_registry_file(path: str) -> Tuple[bool, List[str]]:
    """Load and validate a registry YAML file."""
    if yaml is None:
        return (False, ["PyYAML is not installed"])
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return (False, [f"Failed to load registry file: {e}"])
    return validate_registry(data)
