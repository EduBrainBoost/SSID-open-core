"""
SSID Health Check Template
Reads real registry/evidence data instead of hardcoded status.
"""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Resolve paths relative to this module
_MODULE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _MODULE_DIR / "health_config.yaml"
_WORKSPACE_ROOT = _MODULE_DIR.parents[1]  # two levels up -> repo root


def _load_config() -> dict:
    """Load health_config.yaml."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Health config not found: {_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _file_exists(relative_path: str) -> bool:
    """Check whether a file exists relative to workspace root."""
    return (_WORKSPACE_ROOT / relative_path).exists()


def _sha256_of_file(path: Path) -> str | None:
    """Return SHA-256 hex digest of a file, or None if missing."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _evaluate_check(name: str, path: str) -> dict[str, Any]:
    """Evaluate a single required-file check."""
    full = _WORKSPACE_ROOT / path
    exists = full.exists()
    return {
        "name": name,
        "path": path,
        "exists": exists,
        "sha256": _sha256_of_file(full) if exists else None,
        "status": "pass" if exists else "fail",
    }


def check_health(root_type: str = "default") -> dict[str, Any]:
    """
    Run health checks for a given root type.

    Returns dict with:
        status     – "healthy" | "degraded" | "down"
        checks     – list of individual check results
        timestamp  – ISO-8601 UTC timestamp
        root_type  – which config profile was used
    """
    config = _load_config()
    thresholds = config.get("thresholds", {"healthy": 100, "degraded": 50})
    required = config.get("required_checks", {}).get(root_type, [])

    if not required:
        required = config.get("required_checks", {}).get("default", [])

    checks: list[dict[str, Any]] = []
    for entry in required:
        checks.append(_evaluate_check(entry["name"], entry["path"]))

    total = len(checks)
    passed = sum(1 for c in checks if c["status"] == "pass")
    pct = (passed / total * 100) if total > 0 else 0

    if pct >= thresholds["healthy"]:
        status = "healthy"
    elif pct >= thresholds["degraded"]:
        status = "degraded"
    else:
        status = "down"

    return {
        "status": status,
        "checks": checks,
        "passed": passed,
        "total": total,
        "percent": round(pct, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "root_type": root_type,
    }
