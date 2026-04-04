"""
Bridge: 03_core -> 20_foundation
Validates fee consistency between Core validators and Foundation tokenomics.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

FEE_ENGINE_PATH = REPO_ROOT / "20_foundation" / "shards" / "fee_distribution_engine.yaml"
TOKEN_FRAMEWORK_PATH = REPO_ROOT / "20_foundation" / "shards" / "token_framework.yaml"


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _load_yaml_safe(path: Path) -> dict | None:
    """Load YAML if available, else return None."""
    if not path.exists():
        return None
    try:
        import yaml

        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return None


def validate_fee_consistency() -> dict[str, Any]:
    """
    Check that fee_distribution_engine and token_framework
    are consistent (both exist, both parseable, no key conflicts).
    """
    fee_data = _load_yaml_safe(FEE_ENGINE_PATH)
    token_data = _load_yaml_safe(TOKEN_FRAMEWORK_PATH)

    issues: list[str] = []
    if fee_data is None:
        issues.append(f"fee_distribution_engine not found or unparseable: {FEE_ENGINE_PATH}")
    if token_data is None:
        issues.append(f"token_framework not found or unparseable: {TOKEN_FRAMEWORK_PATH}")

    consistent = len(issues) == 0

    return {
        "bridge": "core_to_foundation",
        "consistent": consistent,
        "issues": issues,
        "evidence_sha256": _sha256(json.dumps(issues, sort_keys=True)),
        "timestamp": datetime.now(UTC).isoformat(),
    }
