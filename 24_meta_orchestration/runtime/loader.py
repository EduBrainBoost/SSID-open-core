"""
SSIDCTL v2 Registry Loader — loads registry, profiles, legacy mapping.
Supports YAML (canonical) with JSON fallback.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


@dataclass(frozen=True)
class AgentDef:
    agent_id: str
    status: str
    level: str
    repo_scope: List[str]
    root_scope: List[str]
    shard_scope: List[str]
    purpose: str
    skills: List[str]
    allowed_paths: List[str]
    forbidden_paths: List[str]
    inputs: List[str]
    outputs: List[str]
    done_criteria: str
    activation_conditions: List[str]
    depends_on: List[str]
    writes_allowed: bool
    can_touch_canonical: bool
    risk_class: str
    human_name: str = ""
    execution_mode: str = ""
    priority: str = "normal"


@dataclass
class ProfileDef:
    profile_id: str
    description: str
    activation_rule: str
    agents: List[str]
    gate_condition: str
    use_case: str
    phase_a_agents: List[str] = field(default_factory=list)
    phase_b_agents: List[str] = field(default_factory=list)


@dataclass
class LegacyMapping:
    legacy_id: str
    legacy_file: str
    retained_as_legacy: bool
    mapped_to: List[str]
    replacement_strategy: str
    migration_note: str


@dataclass
class RegistryBundle:
    schema_version: str
    total_agents: int
    layer_counts: Dict[str, int]
    global_rules: Dict[str, Any]
    agents: Dict[str, AgentDef]
    profiles: Dict[str, ProfileDef]
    legacy_mappings: List[LegacyMapping]


def _parse_agent(data: dict) -> AgentDef:
    return AgentDef(
        agent_id=data["agent_id"],
        status=data.get("status", "active"),
        level=data["level"],
        repo_scope=list(data.get("repo_scope", [])),
        root_scope=list(data.get("root_scope", [])),
        shard_scope=list(data.get("shard_scope", [])),
        purpose=data.get("purpose", ""),
        skills=list(data.get("skills", [])),
        allowed_paths=list(data.get("allowed_paths", [])),
        forbidden_paths=list(data.get("forbidden_paths", [])),
        inputs=list(data.get("inputs", [])),
        outputs=list(data.get("outputs", [])),
        done_criteria=data.get("done_criteria", ""),
        activation_conditions=list(data.get("activation_conditions", [])),
        depends_on=list(data.get("depends_on", [])),
        writes_allowed=bool(data.get("writes_allowed", False)),
        can_touch_canonical=bool(data.get("can_touch_canonical", False)),
        risk_class=data.get("risk_class", ""),
        human_name=data.get("human_name", ""),
        execution_mode=data.get("execution_mode", ""),
        priority=data.get("priority", "normal"),
    )


def _parse_profile(data: dict) -> ProfileDef:
    return ProfileDef(
        profile_id=data["profile_id"],
        description=data.get("description", ""),
        activation_rule=data.get("activation_rule", ""),
        agents=list(data.get("agents", [])),
        gate_condition=data.get("gate_condition", ""),
        use_case=data.get("use_case", ""),
        phase_a_agents=list(data.get("phase_a_agents", [])),
        phase_b_agents=list(data.get("phase_b_agents", [])),
    )


def _parse_legacy(data: dict) -> LegacyMapping:
    return LegacyMapping(
        legacy_id=data["legacy_id"],
        legacy_file=data.get("legacy_file", ""),
        retained_as_legacy=bool(data.get("retained_as_legacy", True)),
        mapped_to=list(data.get("mapped_to", [])),
        replacement_strategy=data.get("replacement_strategy", ""),
        migration_note=data.get("migration_note", ""),
    )


def _load_file(path: Path) -> dict:
    """Load YAML or JSON file. YAML preferred, JSON fallback."""
    if _HAS_YAML and path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(base: Path, name_stem: str) -> Path:
    """Find YAML first, then JSON."""
    yaml_path = base / f"{name_stem}.yaml"
    if _HAS_YAML and yaml_path.exists():
        return yaml_path
    json_path = base / f"{name_stem}.json"
    if json_path.exists():
        return json_path
    raise FileNotFoundError(f"Neither {yaml_path} nor {json_path} found")


def load_registry(registry_path: Path) -> tuple:
    """Load registry (YAML or JSON), return (raw_data, agents_dict)."""
    raw = _load_file(registry_path)
    agents = {}
    for a in raw.get("agents", []):
        agent = _parse_agent(a)
        agents[agent.agent_id] = agent
    return raw, agents


def load_profiles(profiles_path: Path) -> Dict[str, ProfileDef]:
    raw = _load_file(profiles_path)
    profiles = {}
    for p in raw.get("profiles", []):
        prof = _parse_profile(p)
        profiles[prof.profile_id] = prof
    return profiles


def load_legacy_mapping(mapping_path: Path) -> List[LegacyMapping]:
    raw = _load_file(mapping_path)
    return [_parse_legacy(m) for m in raw.get("mappings", [])]


def load_bundle(repo_root: Path) -> RegistryBundle:
    """Load all v2 registry artifacts into a single bundle.
    Prefers YAML (canonical), falls back to JSON.
    """
    reg_dir = repo_root / "24_meta_orchestration" / "registry"
    registry_path = _resolve_path(reg_dir, "ssidctl_agent_registry.v2")
    profiles_path = _resolve_path(reg_dir, "ssidctl_activation_profiles.v2")
    mapping_path = _resolve_path(reg_dir, "ssidctl_legacy_mapping.v2")

    raw, agents = load_registry(registry_path)
    profiles = load_profiles(profiles_path)
    legacy = load_legacy_mapping(mapping_path)

    return RegistryBundle(
        schema_version=raw.get("schema_version", "1.0.0"),
        total_agents=raw.get("total_agents", len(agents)),
        layer_counts=raw.get("layer_counts", {}),
        global_rules=raw.get("global_rules", {}),
        agents=agents,
        profiles=profiles,
        legacy_mappings=legacy,
    )
