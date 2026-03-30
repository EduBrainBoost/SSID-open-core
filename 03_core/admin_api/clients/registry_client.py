"""Registry client — reads admin dashboard registry from meta_orchestration."""

from __future__ import annotations

import json
import os
from typing import Any


def load_registry(name: str = "admin_dashboard_registry.json") -> dict[str, Any]:
    """Load a registry JSON from 24_meta_orchestration/registry/."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "24_meta_orchestration", "registry", name
    )
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"status": "not_found", "path": path}
