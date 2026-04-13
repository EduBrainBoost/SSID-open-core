"""
SSIDCTL v2 Lock / Path / Policy Enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .loader import AgentDef

CANONICAL_MARKERS = ("Documents\\Github", "Documents/Github")


@dataclass
class EnforcementResult:
    passed: bool
    violations: list[str]


def check_canonical_write(agent: AgentDef) -> EnforcementResult:
    """Verify agent cannot touch canonical zone."""
    if agent.can_touch_canonical:
        return EnforcementResult(
            passed=False,
            violations=[f"{agent.agent_id}: can_touch_canonical=true — forbidden"],
        )
    return EnforcementResult(passed=True, violations=[])


def check_forbidden_paths(agent: AgentDef, target_path: str) -> EnforcementResult:
    """Check if target_path violates agent's forbidden_paths."""
    norm = target_path.replace("\\", "/")
    violations = []
    for fp in agent.forbidden_paths:
        fp_norm = fp.replace("\\", "/").rstrip("/*")
        if fp_norm and fp_norm in norm:
            violations.append(f"{agent.agent_id}: path '{target_path}' matches forbidden '{fp}'")
    # Always block canonical zone
    for marker in CANONICAL_MARKERS:
        if marker.replace("\\", "/") in norm:
            violations.append(f"{agent.agent_id}: path '{target_path}' is in canonical zone")
    if violations:
        return EnforcementResult(passed=False, violations=violations)
    return EnforcementResult(passed=True, violations=[])


def check_allowed_paths(agent: AgentDef, target_path: str) -> EnforcementResult:
    """Check if target_path is within agent's allowed_paths."""
    if not agent.allowed_paths:
        return EnforcementResult(passed=True, violations=[])
    norm = target_path.replace("\\", "/")
    for ap in agent.allowed_paths:
        ap_norm = ap.replace("\\", "/").rstrip("/*").split(" (")[0]
        if not ap_norm:
            continue
        if ap_norm == "**/" or ap_norm == "**/":
            return EnforcementResult(passed=True, violations=[])
        if norm.startswith(ap_norm) or ap_norm in norm:
            return EnforcementResult(passed=True, violations=[])
    return EnforcementResult(
        passed=False,
        violations=[f"{agent.agent_id}: path '{target_path}' not in allowed_paths"],
    )


def check_root24_lock(repo_root: Path) -> EnforcementResult:
    """Verify ROOT-24-LOCK: exactly 24 canonical roots exist."""
    expected = {
        "01_ai_layer",
        "02_audit_logging",
        "03_core",
        "04_deployment",
        "05_documentation",
        "06_data_pipeline",
        "07_governance_legal",
        "08_identity_score",
        "09_meta_identity",
        "10_interoperability",
        "11_test_simulation",
        "12_tooling",
        "13_ui_layer",
        "14_zero_time_auth",
        "15_infra",
        "16_codex",
        "17_observability",
        "18_data_layer",
        "19_adapters",
        "20_foundation",
        "21_post_quantum_crypto",
        "22_datasets",
        "23_compliance",
        "24_meta_orchestration",
    }
    actual = set()
    violations = []
    for item in repo_root.iterdir():
        if item.is_dir() and item.name[:2].isdigit() and "_" in item.name:
            actual.add(item.name)

    missing = expected - actual
    extra = actual - expected
    if missing:
        violations.append(f"missing roots: {sorted(missing)}")
    if extra:
        violations.append(f"unexpected roots: {sorted(extra)}")

    return EnforcementResult(passed=not violations, violations=violations)


def enforce_all_agents(agents: list[AgentDef]) -> EnforcementResult:
    """Run baseline enforcement checks across all resolved agents."""
    all_violations = []
    for agent in agents:
        r = check_canonical_write(agent)
        all_violations.extend(r.violations)
    return EnforcementResult(
        passed=not all_violations,
        violations=all_violations,
    )


@dataclass
class LockState:
    locked: bool = False
    lock_holder: str = ""
    lock_path: Path | None = None


def acquire_lock(lock_dir: Path, agent_id: str) -> LockState:
    """Acquire a simple file-based lock for an agent scope."""
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / f"{agent_id.replace('.', '_')}.lock"
    if lock_file.exists():
        holder = lock_file.read_text(encoding="utf-8").strip()
        return LockState(locked=False, lock_holder=holder, lock_path=lock_file)
    lock_file.write_text(agent_id, encoding="utf-8")
    return LockState(locked=True, lock_holder=agent_id, lock_path=lock_file)


def release_lock(lock_state: LockState) -> None:
    """Release a previously acquired lock."""
    if lock_state.lock_path and lock_state.lock_path.exists():
        lock_state.lock_path.unlink()
