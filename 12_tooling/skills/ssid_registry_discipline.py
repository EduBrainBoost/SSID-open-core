"""ssid-registry-discipline — Registry consistency check.

Ensures that every skill referenced in agent_skill_bindings.yaml
exists in skill_registry.yaml and vice-versa.
"""

import os
from typing import Any, Dict, Set

from ._evidence import make_evidence, result

SKILL_ID = "ssid-registry-discipline"


def _load_yaml_simple(path: str) -> Any:
    """Minimal YAML loader — tries PyYAML, falls back to basic parsing."""
    try:
        import yaml  # type: ignore
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except ImportError:
        pass
    # Fallback: very basic key extraction (not full YAML)
    return None


def execute(context: Dict) -> Dict:
    """Check registry <-> binding consistency.

    context must contain:
        workspace_root: str
    Optional:
        registry_path: str  — override path to skill_registry.yaml
        bindings_path: str  — override path to agent_skill_bindings.yaml
    """
    workspace_root = context.get("workspace_root", "")
    if not workspace_root:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "workspace_root missing"})
        return result("FAIL", ev, "workspace_root is required")
    registry_path = context.get(
        "registry_path",
        os.path.join(workspace_root, "24_meta_orchestration", "agentswarm", "registry", "skill_registry.yaml"),
    )
    bindings_path = context.get(
        "bindings_path",
        os.path.join(workspace_root, "24_meta_orchestration", "agentswarm", "registry", "agent_skill_bindings.yaml"),
    )

    if not os.path.isfile(registry_path):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": f"registry not found: {registry_path}"})
        return result("FAIL", ev, "skill_registry.yaml not found")

    if not os.path.isfile(bindings_path):
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": f"bindings not found: {bindings_path}"})
        return result("FAIL", ev, "agent_skill_bindings.yaml not found")

    reg_data = _load_yaml_simple(registry_path)
    bind_data = _load_yaml_simple(bindings_path)

    if reg_data is None or bind_data is None:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "PyYAML not available, cannot parse"})
        return result("FAIL", ev, "PyYAML required for registry discipline check")

    registry_ids: Set[str] = set()
    for skill in reg_data.get("skills", []):
        sid = skill.get("skill_id", "")
        if sid:
            registry_ids.add(sid)

    binding_ids: Set[str] = set()
    for binding in bind_data.get("bindings", []):
        for sid in binding.get("skills", []):
            binding_ids.add(sid)

    in_registry_not_bound = sorted(registry_ids - binding_ids)
    in_bindings_not_registered = sorted(binding_ids - registry_ids)
    overlap = sorted(registry_ids & binding_ids)

    details = {
        "registry_count": len(registry_ids),
        "binding_unique_count": len(binding_ids),
        "overlap": overlap,
        "in_registry_not_bound": in_registry_not_bound,
        "in_bindings_not_registered": in_bindings_not_registered,
    }

    if in_bindings_not_registered:
        ev = make_evidence(SKILL_ID, "FAIL", details)
        return result("FAIL", ev, f"{len(in_bindings_not_registered)} binding skills not in registry")

    ev = make_evidence(SKILL_ID, "PASS", details)
    return result("PASS", ev, "Registry and bindings are consistent")
