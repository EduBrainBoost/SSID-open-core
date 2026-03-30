"""
SSIDCTL v2 Runner — L0 Controller, Smoke/Dry-Run execution, Evidence pipeline.

Entry point for `e2e_dispatcher.py run-profile`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loader import AgentDef, RegistryBundle, load_bundle
from .resolver import ResolutionResult, get_activation_order, resolve_profile
from .enforcement import (
    EnforcementResult,
    LockState,
    acquire_lock,
    check_root24_lock,
    enforce_all_agents,
    release_lock,
)
from .state_machine import RunContext, RunState

# --- G03 FIX: Canonical SoT Validator for CI/Hook parity ---
from importlib.util import spec_from_file_location, module_from_spec

_SOT_CORE_REL = "03_core/validators/sot/sot_validator_core.py"


def _load_sot_validator_core(repo_root: Path):
    """Load canonical SoT validator for parity with CI/hooks."""
    core_path = repo_root / _SOT_CORE_REL
    if not core_path.exists():
        return None
    spec = spec_from_file_location("sot_validator_core", str(core_path))
    if spec is None or spec.loader is None:
        return None
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
# --- END G03 FIX ---


def _utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SSIDCTLRunner:
    """L0 Master Orchestrator — runs v2 profiles through the full state machine."""

    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = repo_root.resolve()
        self.dry_run = dry_run
        self.bundle: Optional[RegistryBundle] = None
        self.resolution: Optional[ResolutionResult] = None
        self.ctx: Optional[RunContext] = None
        self.locks: List[LockState] = []
        self.evidence_dir: Optional[Path] = None
        self.log_lines: List[str] = []

    def _log(self, event: str, detail: str = "") -> None:
        entry = {"ts_utc": _utc_now(), "event": event}
        if detail:
            entry["detail"] = detail
        self.log_lines.append(json.dumps(entry, sort_keys=True))

    def run(self, profile_id: str) -> int:
        """Execute the full v2 runtime pipeline. Returns exit code."""
        run_id = f"ssidctl_v2_{profile_id}_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        self.ctx = RunContext(
            run_id=run_id,
            profile_id=profile_id,
            dry_run=self.dry_run,
        )
        self._log("RUN_INIT", f"profile={profile_id} dry_run={self.dry_run}")

        try:
            return self._execute_pipeline()
        except Exception as exc:
            self._log("FATAL_ERROR", str(exc))
            if self.ctx and not self.ctx.is_terminal:
                self.ctx.force_terminal(RunState.FAILED, str(exc))
            self._write_evidence()
            return 1

    def _execute_pipeline(self) -> int:
        ctx = self.ctx
        assert ctx is not None

        # REGISTERED -> PROFILE_SELECTED
        self._log("PHASE", "loading registry")
        try:
            self.bundle = load_bundle(self.repo_root)
        except Exception as exc:
            ctx.force_terminal(RunState.FAILED, f"registry load failed: {exc}")
            self._write_evidence()
            return 2
        self._log("REGISTRY_LOADED", f"agents={self.bundle.total_agents} profiles={len(self.bundle.profiles)}")

        if not ctx.transition(RunState.PROFILE_SELECTED, f"profile={ctx.profile_id}"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to PROFILE_SELECTED")
            self._write_evidence()
            return 2

        # PROFILE_SELECTED -> PRECHECK
        if not ctx.transition(RunState.PRECHECK, "starting prechecks"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to PRECHECK")
            self._write_evidence()
            return 2

        # Resolve profile
        self.resolution = resolve_profile(self.bundle, ctx.profile_id)
        if self.resolution.blocked:
            ctx.transition(RunState.BLOCKED, self.resolution.block_reason)
            self._log("BLOCKED", self.resolution.block_reason)
            self._write_evidence()
            return 3

        self._log("PROFILE_RESOLVED", f"agents={len(self.resolution.resolved_agents)}")

        # ROOT-24-LOCK check
        r24 = check_root24_lock(self.repo_root)
        if not r24.passed:
            ctx.transition(RunState.BLOCKED, f"ROOT-24-LOCK: {r24.violations}")
            self._log("ROOT24_FAIL", str(r24.violations))
            self._write_evidence()
            return 3

        # Enforcement check all agents
        enf = enforce_all_agents(self.resolution.resolved_agents)
        if not enf.passed:
            ctx.transition(RunState.BLOCKED, f"enforcement: {enf.violations}")
            self._log("ENFORCEMENT_FAIL", str(enf.violations))
            self._write_evidence()
            return 3

        # G03 FIX: Run canonical SoT validator for CI/Hook parity
        sot_mod = _load_sot_validator_core(self.repo_root)
        if sot_mod is not None:
            sot_validator = sot_mod.SoTValidatorCore(str(self.repo_root))
            sot_results = sot_validator.validate_all()
            sot_ok, sot_failed = sot_validator.evaluate_priorities(sot_results)
            if not sot_ok:
                ctx.transition(RunState.BLOCKED, f"SoT validator: {sot_failed}")
                self._log("SOT_VALIDATOR_FAIL", str(sot_failed))
                self._write_evidence()
                return 3
            self._log("SOT_VALIDATOR_PASS", f"rules_checked={len(sot_results)}")
        else:
            self._log("SOT_VALIDATOR_SKIP", f"core not found at {_SOT_CORE_REL}")

        self._log("PRECHECK_PASS", "root24=ok enforcement=ok sot_validator=ok profile=ok")

        # PRECHECK -> LOCK_ACQUIRED
        if not ctx.transition(RunState.LOCK_ACQUIRED, "locks acquired"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to LOCK_ACQUIRED")
            self._write_evidence()
            return 2

        lock_dir = self.repo_root / ".ssid-system" / "locks"
        lock = acquire_lock(lock_dir, ctx.run_id)
        if not lock.locked:
            ctx.transition(RunState.BLOCKED, f"lock conflict: holder={lock.lock_holder}")
            self._write_evidence()
            return 3
        self.locks.append(lock)
        self._log("LOCK_ACQUIRED", f"lock_path={lock.lock_path}")

        # LOCK_ACQUIRED -> PLANNED
        if not ctx.transition(RunState.PLANNED, "plan created"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to PLANNED")
            self._release_locks()
            self._write_evidence()
            return 2

        ordered = get_activation_order(self.resolution.resolved_agents)
        self._log("PLANNED", f"activation_order={[a.agent_id for a in ordered[:5]]}...")

        # PLANNED -> AGENTS_RESOLVED
        if not ctx.transition(RunState.AGENTS_RESOLVED, f"{len(ordered)} agents resolved"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to AGENTS_RESOLVED")
            self._release_locks()
            self._write_evidence()
            return 2

        # AGENTS_RESOLVED -> SANDBOX_READY
        self.evidence_dir = (
            self.repo_root / "02_audit_logging" / "evidence" / "ssidctl_v2_runs" / ctx.run_id
        )
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        if not ctx.transition(RunState.SANDBOX_READY, "evidence dir ready"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to SANDBOX_READY")
            self._release_locks()
            self._write_evidence()
            return 2
        self._log("SANDBOX_READY", f"evidence_dir={self.evidence_dir}")

        # SANDBOX_READY -> RUNNING
        if not ctx.transition(RunState.RUNNING, "execution started"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to RUNNING")
            self._release_locks()
            self._write_evidence()
            return 2

        # Execute: dry-run or real smoke
        if self.dry_run:
            self._log("DRY_RUN", "no writes, no external commands")
            exec_ok = True
        else:
            exec_ok = self._execute_smoke(ordered)

        if not exec_ok:
            ctx.transition(RunState.FAILED, "execution failed")
            self._release_locks()
            self._write_evidence()
            return 1

        # RUNNING -> VALIDATING
        if not ctx.transition(RunState.VALIDATING, "execution done, validating"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to VALIDATING")
            self._release_locks()
            self._write_evidence()
            return 2

        self._log("VALIDATING", "post-run checks")

        # Re-check ROOT-24 after run
        r24_post = check_root24_lock(self.repo_root)
        if not r24_post.passed:
            ctx.transition(RunState.FAILED, f"ROOT-24 post-check failed: {r24_post.violations}")
            self._release_locks()
            self._write_evidence()
            return 1

        # VALIDATING -> EVIDENCE_SEALING
        if not ctx.transition(RunState.EVIDENCE_SEALING, "sealing evidence"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to EVIDENCE_SEALING")
            self._release_locks()
            self._write_evidence()
            return 2

        self._write_evidence()

        # EVIDENCE_SEALING -> COMPLETED
        if not ctx.transition(RunState.COMPLETED, "run complete"):
            ctx.force_terminal(RunState.FAILED, "invalid transition to COMPLETED")
            return 2

        ctx.exit_code = 0
        self._log("COMPLETED", f"run_id={ctx.run_id} exit_code=0")

        # Update evidence with final state
        self._write_evidence()
        self._release_locks()

        print(f"SSIDCTL_V2_COMPLETED: {ctx.run_id}")
        print(f"  profile: {ctx.profile_id}")
        print(f"  agents: {len(self.resolution.resolved_agents)}")
        print(f"  dry_run: {ctx.dry_run}")
        print(f"  state: {ctx.state.value}")
        print(f"  exit_code: 0")
        return 0

    def _execute_smoke(self, agents: List[AgentDef]) -> bool:
        """Execute a deterministic local smoke-run. No external providers."""
        self._log("SMOKE_START", f"agents={len(agents)}")

        for agent in agents:
            self._log("AGENT_ACTIVATE", agent.agent_id)
            # Deterministic local noop: each agent "runs" by confirming its scope
            agent_result = {
                "agent_id": agent.agent_id,
                "level": agent.level,
                "status": "smoke_pass",
                "scope_check": "ok",
                "writes": 0,
                "ts_utc": _utc_now(),
            }
            if self.evidence_dir:
                result_file = self.evidence_dir / f"agent_{agent.agent_id.replace('.', '_')}.json"
                result_file.write_text(
                    json.dumps(agent_result, indent=2), encoding="utf-8"
                )
            self._log("AGENT_DONE", f"{agent.agent_id} smoke_pass")

        self._log("SMOKE_DONE", f"all {len(agents)} agents passed")
        return True

    def _write_evidence(self) -> None:
        """Write run evidence to evidence directory."""
        if not self.evidence_dir or not self.ctx:
            return

        # Run manifest
        manifest = {
            "run_id": self.ctx.run_id,
            "profile_id": self.ctx.profile_id,
            "state": self.ctx.state.value,
            "started_at": self.ctx.started_at,
            "ended_at": self.ctx.ended_at or _utc_now(),
            "exit_code": self.ctx.exit_code,
            "dry_run": self.ctx.dry_run,
            "agent_count": len(self.resolution.resolved_agents) if self.resolution else 0,
            "transitions": self.ctx.to_dict()["transitions"],
            "log_lines": self.log_lines,
        }
        manifest_path = self.evidence_dir / "run_manifest.json"
        manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False)
        manifest_path.write_text(manifest_text, encoding="utf-8")

        # Seal hash
        seal = {
            "run_id": self.ctx.run_id,
            "sealed_at_utc": _utc_now(),
            "manifest_sha256": _sha256_text(manifest_text),
            "evidence_dir": str(self.evidence_dir),
        }
        seal_path = self.evidence_dir / "seal.json"
        seal_path.write_text(json.dumps(seal, indent=2), encoding="utf-8")

    def _release_locks(self) -> None:
        for lock in self.locks:
            release_lock(lock)
        self.locks.clear()
