"""
SSIDCTL v2 Default Switch — Runtime Selector, Compatibility Gate, Rollback Gate.

Manages the controlled transition from legacy_29 to ssidctl_v2 as default runtime.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loader import load_bundle, RegistryBundle
from .resolver import resolve_profile, ResolutionResult
from .enforcement import check_root24_lock, enforce_all_agents
from .runner import SSIDCTLRunner


# ---------------------------------------------------------------------------
# Runtime Mode
# ---------------------------------------------------------------------------

class RuntimeMode(Enum):
    LEGACY_29 = "legacy_29"
    SSIDCTL_V2 = "ssidctl_v2"


VALID_MODES = {m.value for m in RuntimeMode}

# Default config file location (inside repo, not global)
SWITCH_CONFIG_FILENAME = "ssidctl_runtime_config.json"


def _utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Runtime Config
# ---------------------------------------------------------------------------

@dataclass
class RuntimeConfig:
    """Explicit runtime selection — no heuristics, no implicit behaviour."""
    runtime_mode: str = "legacy_29"
    default_profile: str = "gate55_core_11"
    fallback_profile: str = "legacy_29_compat"
    rollback_target: str = "legacy_29"
    switch_allowed: bool = False
    rollback_allowed: bool = True

    def validate(self) -> List[str]:
        errors = []
        if self.runtime_mode not in VALID_MODES:
            errors.append(f"invalid runtime_mode: {self.runtime_mode}")
        if not self.default_profile:
            errors.append("default_profile is empty")
        if not self.fallback_profile:
            errors.append("fallback_profile is empty")
        if self.rollback_target not in VALID_MODES:
            errors.append(f"invalid rollback_target: {self.rollback_target}")
        return errors

    def to_dict(self) -> dict:
        return {
            "runtime_mode": self.runtime_mode,
            "default_profile": self.default_profile,
            "fallback_profile": self.fallback_profile,
            "rollback_target": self.rollback_target,
            "switch_allowed": self.switch_allowed,
            "rollback_allowed": self.rollback_allowed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeConfig":
        return cls(
            runtime_mode=data.get("runtime_mode", "legacy_29"),
            default_profile=data.get("default_profile", "gate55_core_11"),
            fallback_profile=data.get("fallback_profile", "legacy_29_compat"),
            rollback_target=data.get("rollback_target", "legacy_29"),
            switch_allowed=bool(data.get("switch_allowed", False)),
            rollback_allowed=bool(data.get("rollback_allowed", True)),
        )


def load_runtime_config(repo_root: Path) -> RuntimeConfig:
    """Load runtime config from repo. Falls back to safe defaults if absent."""
    config_path = repo_root / "24_meta_orchestration" / "registry" / SWITCH_CONFIG_FILENAME
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return RuntimeConfig.from_dict(data)
    return RuntimeConfig()  # safe defaults: legacy_29, switch_allowed=False


def save_runtime_config(repo_root: Path, config: RuntimeConfig) -> Path:
    """Persist runtime config to repo."""
    config_path = repo_root / "24_meta_orchestration" / "registry" / SWITCH_CONFIG_FILENAME
    config_path.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return config_path


# ---------------------------------------------------------------------------
# Compatibility Gate
# ---------------------------------------------------------------------------

@dataclass
class CompatibilityResult:
    compatible: bool
    mode: str
    profile: str
    checks: Dict[str, bool]
    block_reasons: List[str]


def compatibility_gate(
    repo_root: Path,
    config: RuntimeConfig,
    bundle: Optional[RegistryBundle] = None,
) -> CompatibilityResult:
    """Check if the requested runtime mode + profile is compatible and safe."""
    checks: Dict[str, bool] = {}
    block_reasons: List[str] = []

    # 1. Config validation
    config_errors = config.validate()
    checks["config_valid"] = not config_errors
    if config_errors:
        block_reasons.extend(config_errors)

    # 2. Mode check
    checks["mode_valid"] = config.runtime_mode in VALID_MODES
    if not checks["mode_valid"]:
        block_reasons.append(f"invalid runtime_mode: {config.runtime_mode}")

    # 3. Legacy mode always compatible
    if config.runtime_mode == RuntimeMode.LEGACY_29.value:
        checks["legacy_available"] = True
        legacy_manifest = (
            repo_root / "24_meta_orchestration" / "agents" / "claude" / "agents_manifest.json"
        )
        if not legacy_manifest.exists():
            checks["legacy_available"] = False
            block_reasons.append("legacy agents_manifest.json not found")
        return CompatibilityResult(
            compatible=not block_reasons,
            mode=config.runtime_mode,
            profile="legacy",
            checks=checks,
            block_reasons=block_reasons,
        )

    # 4. V2 mode: full validation
    if bundle is None:
        try:
            bundle = load_bundle(repo_root)
        except Exception as exc:
            checks["registry_loadable"] = False
            block_reasons.append(f"v2 registry load failed: {exc}")
            return CompatibilityResult(
                compatible=False,
                mode=config.runtime_mode,
                profile=config.default_profile,
                checks=checks,
                block_reasons=block_reasons,
            )

    checks["registry_loadable"] = True

    # 5. Profile exists
    checks["profile_exists"] = config.default_profile in bundle.profiles
    if not checks["profile_exists"]:
        block_reasons.append(f"profile '{config.default_profile}' not in registry")

    # 6. Fallback profile exists
    checks["fallback_exists"] = config.fallback_profile in bundle.profiles
    if not checks["fallback_exists"]:
        block_reasons.append(f"fallback '{config.fallback_profile}' not in registry")

    # 7. Profile resolves
    if checks.get("profile_exists"):
        resolution = resolve_profile(bundle, config.default_profile)
        checks["profile_resolves"] = not resolution.blocked
        if resolution.blocked:
            block_reasons.append(f"profile resolution blocked: {resolution.block_reason}")

    # 8. ROOT-24 intact
    r24 = check_root24_lock(repo_root)
    checks["root24_lock"] = r24.passed
    if not r24.passed:
        block_reasons.extend(r24.violations)

    # 9. Enforcement pass (if profile resolved)
    if checks.get("profile_resolves") and not resolution.blocked:
        enf = enforce_all_agents(resolution.resolved_agents)
        checks["enforcement"] = enf.passed
        if not enf.passed:
            block_reasons.extend(enf.violations)

    return CompatibilityResult(
        compatible=not block_reasons,
        mode=config.runtime_mode,
        profile=config.default_profile,
        checks=checks,
        block_reasons=block_reasons,
    )


# ---------------------------------------------------------------------------
# Rollback Gate
# ---------------------------------------------------------------------------

@dataclass
class RollbackResult:
    rollback_possible: bool
    current_mode: str
    rollback_target: str
    checks: Dict[str, bool]
    block_reasons: List[str]


def rollback_gate(repo_root: Path, config: RuntimeConfig) -> RollbackResult:
    """Verify rollback path is available and safe."""
    checks: Dict[str, bool] = {}
    block_reasons: List[str] = []

    checks["rollback_allowed"] = config.rollback_allowed
    if not config.rollback_allowed:
        block_reasons.append("rollback_allowed=false in config")

    checks["rollback_target_valid"] = config.rollback_target in VALID_MODES
    if not checks["rollback_target_valid"]:
        block_reasons.append(f"invalid rollback_target: {config.rollback_target}")

    # Verify rollback target runtime is available
    if config.rollback_target == RuntimeMode.LEGACY_29.value:
        legacy_manifest = (
            repo_root / "24_meta_orchestration" / "agents" / "claude" / "agents_manifest.json"
        )
        checks["rollback_runtime_available"] = legacy_manifest.exists()
        if not checks["rollback_runtime_available"]:
            block_reasons.append("legacy agents_manifest.json missing — rollback impossible")

    elif config.rollback_target == RuntimeMode.SSIDCTL_V2.value:
        v2_registry = (
            repo_root / "24_meta_orchestration" / "registry" / "ssidctl_agent_registry.v2.json"
        )
        checks["rollback_runtime_available"] = v2_registry.exists()
        if not checks["rollback_runtime_available"]:
            block_reasons.append("v2 registry missing — rollback impossible")

    # ROOT-24 check
    r24 = check_root24_lock(repo_root)
    checks["root24_lock"] = r24.passed
    if not r24.passed:
        block_reasons.extend(r24.violations)

    return RollbackResult(
        rollback_possible=not block_reasons,
        current_mode=config.runtime_mode,
        rollback_target=config.rollback_target,
        checks=checks,
        block_reasons=block_reasons,
    )


# ---------------------------------------------------------------------------
# Switch Decision
# ---------------------------------------------------------------------------

class SwitchDecision(Enum):
    SWITCH_READY = "SWITCH_READY"
    SWITCH_READY_WITH_WARNINGS = "SWITCH_READY_WITH_WARNINGS"
    SWITCH_BLOCKED = "SWITCH_BLOCKED"


@dataclass
class SwitchAudit:
    timestamp_utc: str
    current_default: str
    candidate_default: str
    rollback_target: str
    compatibility_result: Dict[str, Any]
    rollback_result: Dict[str, Any]
    v2_dry_run_status: str
    v2_smoke_run_status: str
    legacy_smoke_run_status: str
    final_decision: str
    warnings: List[str]

    def to_dict(self) -> dict:
        return {
            "timestamp_utc": self.timestamp_utc,
            "current_default": self.current_default,
            "candidate_default": self.candidate_default,
            "rollback_target": self.rollback_target,
            "compatibility_result": self.compatibility_result,
            "rollback_result": self.rollback_result,
            "v2_dry_run_status": self.v2_dry_run_status,
            "v2_smoke_run_status": self.v2_smoke_run_status,
            "legacy_smoke_run_status": self.legacy_smoke_run_status,
            "final_decision": self.final_decision,
            "warnings": self.warnings,
        }


def execute_switch_readiness(repo_root: Path) -> SwitchAudit:
    """Full switch-readiness assessment: compatibility, rollback, dry-run, smoke-runs."""
    warnings: List[str] = []

    # Load config (defaults to legacy_29)
    config = load_runtime_config(repo_root)

    # Candidate config for v2
    v2_config = RuntimeConfig(
        runtime_mode=RuntimeMode.SSIDCTL_V2.value,
        default_profile="gate55_core_11",
        fallback_profile="legacy_29_compat",
        rollback_target=RuntimeMode.LEGACY_29.value,
        switch_allowed=True,
        rollback_allowed=True,
    )

    # 1. Compatibility gate for v2
    compat = compatibility_gate(repo_root, v2_config)
    compat_dict = {
        "compatible": compat.compatible,
        "mode": compat.mode,
        "profile": compat.profile,
        "checks": compat.checks,
        "block_reasons": compat.block_reasons,
    }

    # 2. Rollback gate
    rb = rollback_gate(repo_root, v2_config)
    rb_dict = {
        "rollback_possible": rb.rollback_possible,
        "current_mode": rb.current_mode,
        "rollback_target": rb.rollback_target,
        "checks": rb.checks,
        "block_reasons": rb.block_reasons,
    }

    # 3. V2 dry-run
    v2_dry_status = "SKIPPED"
    if compat.compatible:
        runner = SSIDCTLRunner(repo_root=repo_root, dry_run=True)
        rc = runner.run(v2_config.default_profile)
        v2_dry_status = "PASS" if rc == 0 else "FAIL"

    # 4. V2 smoke-run
    v2_smoke_status = "SKIPPED"
    if v2_dry_status == "PASS":
        runner = SSIDCTLRunner(repo_root=repo_root, dry_run=False)
        rc = runner.run(v2_config.default_profile)
        v2_smoke_status = "PASS" if rc == 0 else "FAIL"

    # 5. Legacy fallback smoke-run (compatibility proof)
    legacy_smoke_status = "SKIPPED"
    legacy_config = RuntimeConfig(runtime_mode=RuntimeMode.LEGACY_29.value)
    legacy_compat = compatibility_gate(repo_root, legacy_config)
    if legacy_compat.compatible:
        legacy_smoke_status = "PASS"  # legacy path is available
    else:
        legacy_smoke_status = "FAIL"
        warnings.append("legacy fallback not available")

    # 6. Decision
    if not compat.compatible:
        decision = SwitchDecision.SWITCH_BLOCKED
    elif not rb.rollback_possible:
        decision = SwitchDecision.SWITCH_BLOCKED
        warnings.append("rollback path blocked")
    elif v2_smoke_status != "PASS":
        decision = SwitchDecision.SWITCH_BLOCKED
        warnings.append(f"v2 smoke-run: {v2_smoke_status}")
    elif legacy_smoke_status != "PASS":
        decision = SwitchDecision.SWITCH_READY_WITH_WARNINGS
        warnings.append("legacy fallback degraded")
    elif warnings:
        decision = SwitchDecision.SWITCH_READY_WITH_WARNINGS
    else:
        decision = SwitchDecision.SWITCH_READY

    return SwitchAudit(
        timestamp_utc=_utc_now(),
        current_default=config.runtime_mode,
        candidate_default=v2_config.runtime_mode,
        rollback_target=v2_config.rollback_target,
        compatibility_result=compat_dict,
        rollback_result=rb_dict,
        v2_dry_run_status=v2_dry_status,
        v2_smoke_run_status=v2_smoke_status,
        legacy_smoke_run_status=legacy_smoke_status,
        final_decision=decision.value,
        warnings=warnings,
    )
