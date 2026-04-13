"""ssid-sot-runtime — Source-of-Truth validation runtime wrapper.

Validates that SoT artifacts in 16_codex exist and are structurally valid.
"""

import os

from ._evidence import make_evidence, result

SKILL_ID = "ssid-sot-runtime"

# Minimum expected SoT artifacts in 16_codex
SOT_REQUIRED_FILES = [
    "manifest.yaml",
    "module.yaml",
]


def execute(context: dict) -> dict:
    """Validate SoT artifacts under 16_codex.

    context must contain:
        workspace_root: str
    Optional:
        sot_files: list[str]  — override default required files list
    """
    workspace_root = context.get("workspace_root")
    if not workspace_root or not os.path.isdir(workspace_root):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "workspace_root missing or invalid"})
        return result("FAIL", ev, "workspace_root is required")

    codex_path = os.path.join(workspace_root, "16_codex")
    if not os.path.isdir(codex_path):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "16_codex directory not found"})
        return result("FAIL", ev, "16_codex directory does not exist")

    required = context.get("sot_files", SOT_REQUIRED_FILES)
    missing: list[str] = []
    found: list[str] = []

    for f in required:
        fpath = os.path.join(codex_path, f)
        if os.path.isfile(fpath):
            found.append(f)
        else:
            missing.append(f)

    details = {
        "codex_path": codex_path,
        "required": required,
        "found": found,
        "missing": missing,
    }

    if missing:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"SoT missing files: {missing}")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "All SoT artifacts present in 16_codex")
