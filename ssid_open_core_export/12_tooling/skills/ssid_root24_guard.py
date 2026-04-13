"""ssid-root24-guard — Validates Root-24-Lock conformity.

Checks that only the 24 canonical root directories exist at repo top level
and none have been added, renamed, or removed.
"""

import importlib.util
import os
from pathlib import Path

from ._evidence import make_evidence, result

SKILL_ID = "ssid-root24-guard"

# Import canonical roots from 03_core/constants.py (Single Source of Truth)
_CONSTANTS_PATH = Path(__file__).resolve().parents[2] / "03_core" / "constants.py"
_spec = importlib.util.spec_from_file_location("core_constants", _CONSTANTS_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CANONICAL_ROOTS = _mod.CANONICAL_ROOTS  # frozenset form


def execute(context: dict) -> dict:
    """Check that workspace_root contains exactly the 24 canonical roots.

    context must contain:
        workspace_root: str  — path to the SSID repo root
    """
    workspace_root = context.get("workspace_root")
    if not workspace_root or not os.path.isdir(workspace_root):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "workspace_root missing or invalid"})
        return result("FAIL", ev, "workspace_root is required and must be a valid directory")

    entries = {
        e
        for e in os.listdir(workspace_root)
        if os.path.isdir(os.path.join(workspace_root, e)) and not e.startswith(".")
    }

    # Filter to numbered roots only (XX_*)
    numbered = {e for e in entries if len(e) > 2 and e[:2].isdigit() and e[2] == "_"}

    missing = CANONICAL_ROOTS - numbered
    extra = numbered - CANONICAL_ROOTS

    details = {
        "canonical_count": len(CANONICAL_ROOTS),
        "found_count": len(numbered),
        "missing": sorted(missing),
        "extra": sorted(extra),
    }

    if missing or extra:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"Root-24 violation: missing={len(missing)}, extra={len(extra)}")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "All 24 canonical roots present, no extras")
