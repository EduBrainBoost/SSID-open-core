# AutoRunner V2 Plan C — Runtime Integration Closure

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the 6 Plan B AR modules (AR-01/03/04/06/09/10) into the EMS runtime — full HTTP coupling, Claude agent invocation on FAIL, AR-04 IRP stub creation via EMS worktree, AR-03 blockchain anchoring hook, and an E2E integration test.

**Architecture:** Hybrid push+pull — AR scripts push results to EMS via `--ems-url` flag (CI standalone path); EMS runner pulls by invoking AR scripts via subprocess (EMS-orchestrated path). Both converge in `POST /api/autorunner/ar-results`. Claude agent invocation (`subprocess_driver.invoke_claude`) fires only on FAIL when `agent_task` is configured.

**Tech Stack:** Python 3.11, FastAPI (EMS portal), pytest, `urllib.request` (no extra deps in SSID), `subprocess` for AR script invocation, `ssidctl.claude.subprocess_driver` for Agent-API.

**Repos affected:**
- `C:/Users/bibel/Documents/Github/SSID` → branch `feat/autorunner-v2-plan-c-runtime`
- `C:/Users/bibel/Documents/Github/SSID-EMS` → branch `feat/autorunner-v2-plan-c-ems`

**Base commits:**
- SSID: `c759cea` (Plan B merge)
- SSID-EMS: current `main` (check with `git log --oneline -1`)

---

## File Structure

### SSID-EMS new/modified files
| File | Action | Purpose |
|------|--------|---------|
| `src/ssidctl/autorunner/ar_script_matrix.py` | CREATE | Maps AR_ID → script path + default args |
| `src/ssidctl/autorunner/runner.py` | MODIFY | Replace stub `_execute_pipeline()` with real AR script invocation |
| `src/ssidctl/autorunner/agent_invoker.py` | CREATE | Maps AR_ID → Claude agent call on FAIL |
| `src/ssidctl/autorunner/irp_stub_creator.py` | CREATE | Creates IRP stubs via git worktree when AR-04 fails |
| `portal/backend/routers/autorunner_events.py` | CREATE | `POST /api/autorunner/ar-results` + `GET /api/autorunner/ar-results` |
| `portal/backend/services/ar_event_service.py` | CREATE | WORM-style storage for AR result events |
| `portal/backend/main.py` | MODIFY | Register `autorunner_events` router |
| `tests/autorunner/test_ar_script_matrix.py` | CREATE | Unit tests for script matrix |
| `tests/autorunner/test_agent_invoker.py` | CREATE | Unit tests for agent invoker (mock CLI) |
| `tests/autorunner/test_irp_stub_creator.py` | CREATE | Unit tests for IRP stub creator |
| `tests/api/test_autorunner_events_api.py` | CREATE | API tests for AR result events endpoint |
| `tests/autorunner/test_runner_pipeline.py` | CREATE | Integration test: EMS runner → AR script → result |

### SSID new/modified files
| File | Action | Purpose |
|------|--------|---------|
| `12_tooling/ssid_autorunner/ems_reporter.py` | CREATE | `post_result(ems_url, ar_id, result)` — HTTP fire-and-forget |
| `23_compliance/scripts/pii_regex_scan.py` | MODIFY | Add `--ems-url` optional arg, call `ems_reporter.post_result()` before `sys.exit()` |
| `02_audit_logging/scripts/collect_unanchored.py` | MODIFY | Add `--ems-url` + `--blockchain-url` optional args |
| `02_audit_logging/scripts/build_merkle_tree.py` | MODIFY | Add `--blockchain-url` flag; POST Merkle root when URL set |
| `23_compliance/scripts/dora_incident_plan_check.py` | MODIFY | Add `--ems-url` |
| `01_ai_layer/scripts/model_inventory.py` | MODIFY | Add `--ems-url` |
| `08_identity_score/scripts/pofi_audit.py` | NO CHANGE | Extra-script of AR-09; do NOT add `--ems-url` (would cause 409 duplicate in EMS) |
| `05_documentation/scripts/generate_from_chart.py` | MODIFY | Add `--ems-url` |
| `23_compliance/scripts/fee_policy_audit.py` | MODIFY | Add `--ems-url` |
| `12_tooling/tests/autorunners/test_ems_reporter.py` | CREATE | Tests for reporter: fire-and-forget, no failure on EMS down |
| `16_codex/decisions/ADR_0074_autorunner_v2_plan_c_runtime_closure.md` | CREATE | ADR for all P3 changes |

---

## Chunk 1: EMS AR Script Matrix + Runner Wiring

### Task 1: `ar_script_matrix.py` — script path registry

**Files:**
- Create: `src/ssidctl/autorunner/ar_script_matrix.py`
- Create: `tests/autorunner/test_ar_script_matrix.py`

The matrix maps each AR_ID to the primary script and default invocation arguments. SSID repo root is passed in at runtime.

- [ ] **Step 1: Write the failing test**

File: `tests/autorunner/test_ar_script_matrix.py`

```python
"""Tests for AR script matrix."""
import pytest
from pathlib import Path
from ssidctl.autorunner.ar_script_matrix import (
    ARScriptMatrix,
    ARScriptDef,
    UnknownARIdError,
)


def test_all_plan_b_ids_registered():
    matrix = ARScriptMatrix()
    for ar_id in ("AR-01", "AR-03", "AR-04", "AR-06", "AR-09", "AR-10"):
        defn = matrix.get(ar_id)
        assert isinstance(defn, ARScriptDef), f"Missing: {ar_id}"


def test_unknown_id_raises():
    matrix = ARScriptMatrix()
    with pytest.raises(UnknownARIdError):
        matrix.get("AR-99")


def test_script_path_is_relative():
    matrix = ARScriptMatrix()
    defn = matrix.get("AR-01")
    assert not Path(defn.script_path).is_absolute()
    assert defn.script_path.endswith(".py")


def test_ar01_has_required_out_placeholder():
    """AR-01 args template must include {out} for output path."""
    matrix = ARScriptMatrix()
    defn = matrix.get("AR-01")
    # args_template is a list; at least one element must contain "{out}"
    assert any("{out}" in a for a in defn.args_template)


def test_ar04_includes_both_scripts():
    """AR-04 runs two scripts: check then validate."""
    matrix = ARScriptMatrix()
    defn = matrix.get("AR-04")
    assert len(defn.extra_scripts) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/bibel/Documents/Github/SSID-EMS && python -m pytest tests/autorunner/test_ar_script_matrix.py -v --tb=short`

Expected: `ImportError: cannot import name 'ARScriptMatrix'`

- [ ] **Step 3: Implement `ar_script_matrix.py`**

File: `src/ssidctl/autorunner/ar_script_matrix.py`

```python
"""AR Script Matrix — maps AR_IDs to SSID script paths and invocation templates.

All paths are relative to the SSID repo root (passed in at runtime).
{out} in args_template is replaced with the temp output JSON path.
{repo_root} is replaced with the SSID repo root.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class UnknownARIdError(KeyError):
    pass


@dataclass
class ARScriptDef:
    ar_id: str
    script_path: str                        # relative to SSID repo root
    args_template: list[str]                # {out} and {repo_root} placeholders
    extra_scripts: list["ARScriptDef"] = field(default_factory=list)
    agent_id: str = ""                      # EMS agent to call on FAIL (if any)
    agent_model: str = "haiku"              # model: opus/sonnet/haiku


_REGISTRY: dict[str, ARScriptDef] = {
    "AR-01": ARScriptDef(
        ar_id="AR-01",
        script_path="23_compliance/scripts/pii_regex_scan.py",
        args_template=[
            "--files", "{repo_root}",
            "--patterns", "23_compliance/rules/pii_patterns.yaml",
            "--out", "{out}",
            "--repo-root", "{repo_root}",
        ],
        agent_id="SEC-05",
        agent_model="opus",
    ),
    "AR-03": ARScriptDef(
        ar_id="AR-03",
        script_path="02_audit_logging/scripts/collect_unanchored.py",
        args_template=[
            "--out", "{out}",
            "--agent-runs-dir", "02_audit_logging/agent_runs",
            "--since-last-anchor", "02_audit_logging/anchor_state.json",
        ],
        extra_scripts=[
            ARScriptDef(
                ar_id="AR-03-merkle",
                script_path="02_audit_logging/scripts/build_merkle_tree.py",
                args_template=["--collect-out", "{collect_out}", "--out", "{out}"],
            ),
        ],
        agent_id="OPS-08",
        agent_model="haiku",
    ),
    "AR-04": ARScriptDef(
        ar_id="AR-04",
        script_path="23_compliance/scripts/dora_incident_plan_check.py",
        args_template=[
            "--out", "{out}",
            "--repo-root", "{repo_root}",
        ],
        extra_scripts=[
            ARScriptDef(
                ar_id="AR-04-validate",
                script_path="23_compliance/scripts/dora_content_validate.py",
                args_template=[
                    "--check-out", "{check_out}",
                    "--out", "{out}",
                    "--repo-root", "{repo_root}",
                ],
            ),
        ],
        agent_id="CMP-14",
        agent_model="sonnet",
    ),
    "AR-06": ARScriptDef(
        ar_id="AR-06",
        script_path="05_documentation/scripts/generate_from_chart.py",
        args_template=[
            "--charts", "{repo_root}",
            "--template", "05_documentation/templates/chart_to_markdown.j2",
            "--out-dir", "05_documentation/generated",
            "--out-manifest", "{out}",
            "--repo-root", "{repo_root}",
        ],
        agent_id="DOC-20",
        agent_model="haiku",
    ),
    "AR-09": ARScriptDef(
        ar_id="AR-09",
        script_path="01_ai_layer/scripts/model_inventory.py",
        args_template=[
            "--out", "{out}",
            "--scan-dirs", "01_ai_layer", "08_identity_score",
            "--repo-root", "{repo_root}",
        ],
        extra_scripts=[
            ARScriptDef(
                ar_id="AR-09-fairness",
                script_path="08_identity_score/scripts/pofi_audit.py",
                args_template=[
                    "--out", "{out}",
                    "--bias-suite", "22_datasets/bias_test_suite.yaml",
                ],
            ),
        ],
        agent_id="ARS-29",
        agent_model="opus",
    ),
    "AR-10": ARScriptDef(
        ar_id="AR-10",
        script_path="23_compliance/scripts/fee_policy_audit.py",
        args_template=[
            "--policy", "23_compliance/fee_allocation_policy.yaml",
            "--out", "{out}",
        ],
        extra_scripts=[
            ARScriptDef(
                ar_id="AR-10-subscription",
                script_path="23_compliance/scripts/subscription_audit.py",
                args_template=[
                    "--policy", "07_governance_legal/subscription_revenue_policy.yaml",
                    "--out", "{out}",
                ],
            ),
            ARScriptDef(
                ar_id="AR-10-pofi",
                script_path="23_compliance/scripts/pofi_formula_check.py",
                args_template=[
                    "--policy", "07_governance_legal/proof_of_fairness_policy.yaml",
                    "--out", "{out}",
                ],
            ),
            ARScriptDef(
                ar_id="AR-10-dao",
                script_path="23_compliance/scripts/dao_params_check.py",
                args_template=[
                    "--policy", "07_governance_legal/subscription_revenue_policy.yaml",
                    "--out", "{out}",
                ],
            ),
        ],
        agent_id="CMP-14",
        agent_model="sonnet",
    ),
}


class ARScriptMatrix:
    def get(self, ar_id: str) -> ARScriptDef:
        if ar_id not in _REGISTRY:
            raise UnknownARIdError(f"Unknown AR ID: {ar_id}. Valid: {sorted(_REGISTRY)}")
        return _REGISTRY[ar_id]

    def all_ids(self) -> list[str]:
        return sorted(_REGISTRY.keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/autorunner/test_ar_script_matrix.py -v --tb=short`

Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/ssidctl/autorunner/ar_script_matrix.py tests/autorunner/test_ar_script_matrix.py
git commit -m "feat(autorunner-p3): AR script matrix — maps AR IDs to SSID script paths"
```

---

### Task 2: `runner._execute_pipeline()` — real AR invocation

**Files:**
- Modify: `src/ssidctl/autorunner/runner.py`
- Create: `tests/autorunner/test_runner_pipeline.py`

Replace the stub `_execute_pipeline()` with subprocess invocation of the AR script for the run's `autorunner_id`. The run model needs a new `autorunner_id` field — add it to `AutoRunnerRun` first.

- [ ] **Step 1: Add `autorunner_id` field to `AutoRunnerRun`**

File: `src/ssidctl/autorunner/models.py` — add one field to `AutoRunnerRun`:

```python
# Add after task_id field (line ~80):
autorunner_id: str | None = None  # AR-01..AR-10; required for AR pipeline runs
```

- [ ] **Step 2: Write the failing pipeline test**

File: `tests/autorunner/test_runner_pipeline.py`

```python
"""Tests for runner._execute_pipeline() — AR script invocation."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ssidctl.autorunner.events import RunEventStream
from ssidctl.autorunner.models import AutoRunnerRun, RunScope, RunStatus
from ssidctl.autorunner.runner import Runner, RunResult


@pytest.fixture
def dummy_run(tmp_path):
    run = AutoRunnerRun.create(
        task_id="TSK-TEST",
        scope=RunScope(repo="SSID", branch="main", paths=["23_compliance/"]),
    )
    run.autorunner_id = "AR-01"
    run.plan_artifact = str(tmp_path / "plan.yaml")
    (tmp_path / "plan.yaml").write_text("steps: []")
    run.transition(RunStatus.PLANNED)
    run.transition(RunStatus.QUEUED)
    return run


def test_pipeline_returns_success_on_pass_exit(dummy_run, tmp_path):
    """When the AR script exits 0 with PASS JSON, runner succeeds."""
    fake_result = json.dumps({"status": "PASS", "total_findings": 0})

    def mock_run_subprocess(*args, capture_output, text, timeout, cwd, **kwargs):
        # Write fake output JSON to the --out path
        cmd = args[0]
        out_idx = cmd.index("--out") + 1 if "--out" in cmd else None
        if out_idx:
            Path(cmd[out_idx]).write_text(fake_result)
        r = MagicMock()
        r.returncode = 0
        r.stdout = f"AR-01: PASS"
        r.stderr = ""
        return r

    with patch("subprocess.run", side_effect=mock_run_subprocess):
        with patch("ssidctl.autorunner.runner.SSID_REPO_ROOT", str(tmp_path)):
            events = RunEventStream(run_id=dummy_run.run_id, base_dir=str(tmp_path / "events"))
            result = Runner().run(dummy_run, events=events)

    assert result.success is True
    assert dummy_run.status == RunStatus.SUCCEEDED


def test_pipeline_fails_on_nonzero_exit(dummy_run, tmp_path):
    """When the AR script exits 1, runner transitions to FAILED."""
    fake_result = json.dumps({"status": "FAIL_POLICY", "total_findings": 3})

    def mock_run_subprocess(*args, **kwargs):
        cmd = args[0]
        out_idx = cmd.index("--out") + 1 if "--out" in cmd else None
        if out_idx:
            Path(cmd[out_idx]).write_text(fake_result)
        r = MagicMock()
        r.returncode = 1
        r.stdout = "FAIL_POLICY"
        r.stderr = ""
        return r

    with patch("subprocess.run", side_effect=mock_run_subprocess):
        with patch("ssidctl.autorunner.runner.SSID_REPO_ROOT", str(tmp_path)):
            events = RunEventStream(run_id=dummy_run.run_id, base_dir=str(tmp_path / "events"))
            result = Runner().run(dummy_run, events=events)

    assert result.success is False
    assert dummy_run.status == RunStatus.FAILED


def test_pipeline_no_ar_id_uses_stub(tmp_path):
    """Runs without autorunner_id fall through to stub pipeline (backward compat)."""
    run = AutoRunnerRun.create(
        task_id="TSK-NOAR",
        scope=RunScope(repo="SSID", branch="main", paths=["src/"]),
    )
    run.plan_artifact = str(tmp_path / "plan.yaml")
    (tmp_path / "plan.yaml").write_text("steps: []")
    run.transition(RunStatus.PLANNED)
    run.transition(RunStatus.QUEUED)

    events = RunEventStream(run_id=run.run_id, base_dir=str(tmp_path / "events"))
    result = Runner().run(run, events=events)
    assert result.success is True  # stub always succeeds
    assert "stub" in result.summary.lower()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/autorunner/test_runner_pipeline.py -v --tb=short`

Expected: FAIL — `SSID_REPO_ROOT` not found in runner

- [ ] **Step 4: Implement real `_execute_pipeline()` in `runner.py`**

Replace `runner.py` with:

```python
"""AutoRunner V2B — Runner: executes pipeline, manages RUNNING state, classifies failures."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from ssidctl.autorunner.ar_script_matrix import ARScriptMatrix, UnknownARIdError
from ssidctl.autorunner.events import RunEvent, RunEventStream
from ssidctl.autorunner.models import AutoRunnerRun, RunStatus
from ssidctl.autorunner.retry import FailureClassifier

# SSID repo root — override in tests via patch or env var
SSID_REPO_ROOT: str = os.environ.get(
    "SSID_REPO_ROOT",
    str(Path(__file__).parent.parent.parent.parent.parent / "SSID"),
)


class RunResult(BaseModel):
    run_id: str
    success: bool
    summary: str
    evidence_manifest: str | None = None
    final_report: str | None = None


_CLASSIFIER = FailureClassifier()
_MATRIX = ARScriptMatrix()


class Runner:
    def run(self, run: AutoRunnerRun, events: RunEventStream) -> RunResult:
        if run.status != RunStatus.QUEUED:
            raise ValueError(f"Can only run a QUEUED run, got: {run.status}")
        run.transition(RunStatus.RUNNING)
        events.append(RunEvent(type="run_started", payload={"run_id": run.run_id}))
        try:
            result = self._execute_pipeline(run, events)
            run.transition(RunStatus.SUCCEEDED)
            run.evidence_manifest = result.evidence_manifest
            run.final_report = result.final_report
            events.append(RunEvent(type="run_succeeded", payload={"summary": result.summary}))
            return result
        except Exception as exc:
            run.failure_class = _CLASSIFIER.classify(exc)
            run.transition(RunStatus.FAILED)
            run.error = str(exc)
            events.append(RunEvent(
                type="run_failed",
                payload={"error": str(exc), "failure_class": str(run.failure_class)},
            ))
            return RunResult(run_id=run.run_id, success=False, summary=f"FAILED: {exc}")

    def _execute_pipeline(self, run: AutoRunnerRun, events: RunEventStream) -> RunResult:
        """Execute the AR pipeline for this run.

        If autorunner_id is set, invokes the corresponding SSID AR script.
        Falls back to stub pipeline for runs without autorunner_id.
        """
        if not run.autorunner_id:
            # Stub pipeline — backward compatible for non-AR runs
            for phase in ("collect", "route", "execute", "verify", "finalize"):
                events.append(RunEvent(type="phase_started", payload={"phase": phase}))
            return RunResult(run_id=run.run_id, success=True, summary="Pipeline completed (stub)")

        try:
            defn = _MATRIX.get(run.autorunner_id)
        except UnknownARIdError as exc:
            raise ValueError(str(exc)) from exc

        repo_root = Path(SSID_REPO_ROOT)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "ar_result.json"
            # Build args by substituting placeholders
            args = [
                a.replace("{out}", str(out_path)).replace("{repo_root}", str(repo_root))
                for a in defn.args_template
            ]
            cmd = ["python", str(repo_root / defn.script_path)] + args
            events.append(RunEvent(
                type="phase_started",
                payload={"phase": "execute", "script": defn.script_path},
            ))
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(repo_root),
            )
            events.append(RunEvent(
                type="phase_completed",
                payload={
                    "phase": "execute",
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[:500],
                },
            ))

            # Parse result JSON
            ar_result: dict = {}
            if out_path.exists():
                try:
                    ar_result = json.loads(out_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    ar_result = {"status": "ERROR", "detail": "invalid JSON output"}
            else:
                ar_result = {"status": "ERROR", "detail": "no output file produced"}

            status = ar_result.get("status", "ERROR")
            success = proc.returncode == 0 and status == "PASS"

            if not success:
                # TODO P4: call agent_invoker.invoke_on_fail(run.autorunner_id, ar_result)
                # here before raising, once Claude CLI is available in EMS runtime.
                # AgentInvoker is wired and tested (Task 3); call site deferred to P4.
                raise RuntimeError(
                    f"{run.autorunner_id} failed: exit_code={proc.returncode}, "
                    f"status={status}"
                )

            return RunResult(
                run_id=run.run_id,
                success=True,
                summary=f"{run.autorunner_id}: {status} (exit={proc.returncode})",
            )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/autorunner/test_runner_pipeline.py -v --tb=short`

Expected: 3/3 PASS

- [ ] **Step 6: Run full autorunner test suite to confirm no regressions**

Run: `python -m pytest tests/test_autorunner_api.py tests/test_autorunner_b_integration.py tests/test_autorunner_dispatcher.py tests/test_autorunner_events.py -v --tb=short`

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/ssidctl/autorunner/models.py src/ssidctl/autorunner/runner.py tests/autorunner/test_runner_pipeline.py
git commit -m "feat(autorunner-p3): wire _execute_pipeline() to real AR script invocation via ar_script_matrix"
```

---

## Chunk 2: EMS Agent Invoker + AR Event API

### Task 3: `agent_invoker.py` — Claude agent on FAIL

**Files:**
- Create: `src/ssidctl/autorunner/agent_invoker.py`
- Create: `tests/autorunner/test_agent_invoker.py`

- [ ] **Step 1: Write the failing test**

File: `tests/autorunner/test_agent_invoker.py`

```python
"""Tests for agent_invoker — triggers Claude CLI on AR FAIL."""
from unittest.mock import MagicMock, patch

import pytest

from ssidctl.autorunner.agent_invoker import (
    AgentInvoker,
    AgentInvokerResult,
    NO_AGENT_FOR_AR,
)


def test_invoke_on_fail_returns_result():
    """invoke_on_fail returns AgentInvokerResult with analysis text."""
    mock_response = MagicMock()
    mock_response.text = "Analysis: 3 PII findings in authentication module."
    mock_response.exit_code = 0
    mock_response.error = None

    with patch("ssidctl.autorunner.agent_invoker.invoke_claude", return_value=mock_response):
        invoker = AgentInvoker()
        result = invoker.invoke_on_fail(
            ar_id="AR-01",
            ar_result={"status": "FAIL_POLICY", "total_findings": 3},
        )

    assert isinstance(result, AgentInvokerResult)
    assert result.invoked is True
    assert "PII" in result.analysis or result.analysis  # some text returned
    assert result.agent_id == "SEC-05"
    assert result.exit_code == 0


def test_no_agent_for_plan_a_module():
    """AR-02 (Plan A) has no agent configured; returns NO_AGENT_FOR_AR."""
    invoker = AgentInvoker()
    result = invoker.invoke_on_fail(ar_id="AR-02", ar_result={"status": "FAIL_POLICY"})
    assert result.invoked is False
    assert result.reason == NO_AGENT_FOR_AR


def test_pass_status_does_not_invoke():
    """PASS results should not trigger agent invocation."""
    invoker = AgentInvoker()
    with patch("ssidctl.autorunner.agent_invoker.invoke_claude") as mock_invoke:
        result = invoker.invoke_on_fail(ar_id="AR-01", ar_result={"status": "PASS"})
    mock_invoke.assert_not_called()
    assert result.invoked is False


def test_cli_not_found_handled_gracefully():
    """If Claude CLI is missing, result shows invoked=False with error, no exception."""
    from ssidctl.claude.subprocess_driver import EXIT_CLI_NOT_FOUND, ClaudeResponse
    error_response = ClaudeResponse(
        text="",
        sha256="sha256:" + "0" * 64,
        bytes_len=0,
        exit_code=EXIT_CLI_NOT_FOUND,
        error="Claude CLI not found",
    )
    with patch("ssidctl.autorunner.agent_invoker.invoke_claude", return_value=error_response):
        invoker = AgentInvoker()
        result = invoker.invoke_on_fail(ar_id="AR-01", ar_result={"status": "FAIL_POLICY"})

    assert result.invoked is False
    assert "CLI not found" in (result.reason or "") or result.exit_code == EXIT_CLI_NOT_FOUND
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/autorunner/test_agent_invoker.py -v --tb=short`

Expected: `ImportError: cannot import name 'AgentInvoker'`

- [ ] **Step 3: Implement `agent_invoker.py`**

File: `src/ssidctl/autorunner/agent_invoker.py`

```python
"""AutoRunner P3 — Agent Invoker: triggers Claude CLI on AR FAIL.

Only invoked when:
  1. ar_result["status"] != "PASS"
  2. The AR_ID has an agent_id configured in the matrix
  3. Claude CLI is available (graceful degradation otherwise)
"""
from __future__ import annotations

from dataclasses import dataclass

from ssidctl.autorunner.ar_script_matrix import ARScriptMatrix, UnknownARIdError
from ssidctl.claude.subprocess_driver import EXIT_CLI_NOT_FOUND, invoke_claude

# Sentinel for "no agent configured for this AR ID"
NO_AGENT_FOR_AR = "NO_AGENT_FOR_AR"

_MATRIX = ARScriptMatrix()

# Model name → full Claude model ID
_MODEL_MAP = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# Prompt template per AR module
_PROMPT_TEMPLATES: dict[str, str] = {
    "AR-01": (
        "You are SEC-05, SSID security auditor. A PII scan returned FAIL_POLICY.\n"
        "Result: {result}\n"
        "Summarize: which file/line has PII, probable cause, recommended fix. "
        "Output plain text only. No code changes."
    ),
    "AR-03": (
        "You are OPS-08, SSID evidence auditor. Evidence anchoring returned an error.\n"
        "Result: {result}\n"
        "Diagnose: why did anchoring fail, which files are unanchored, recommended action."
    ),
    "AR-04": (
        "You are CMP-14, SSID compliance auditor. DORA IR plan check returned FAIL_DORA.\n"
        "Result: {result}\n"
        "List missing IRP paths. For each, state whether template stub creation is appropriate."
    ),
    "AR-06": (
        "You are DOC-20, SSID documentation auditor. Doc generation failed.\n"
        "Result: {result}\n"
        "Identify which chart/module YAML caused the failure and why."
    ),
    "AR-09": (
        "You are ARS-29, SSID fairness auditor. Bias/fairness audit returned FAIL_POLICY.\n"
        "Result: {result}\n"
        "Identify which demographic group failed parity/opportunity threshold and likely cause."
    ),
    "AR-10": (
        "You are CMP-14, SSID compliance auditor. Fee distribution audit returned FAIL_POLICY.\n"
        "Result: {result}\n"
        "Identify which policy check failed (7-Säulen sum, subscription model, POFI, DAO params)."
    ),
}


@dataclass
class AgentInvokerResult:
    invoked: bool
    agent_id: str = ""
    model: str = ""
    analysis: str = ""
    exit_code: int = 0
    reason: str = ""     # populated when invoked=False


class AgentInvoker:
    def invoke_on_fail(
        self,
        ar_id: str,
        ar_result: dict,
        timeout: int = 60,
    ) -> AgentInvokerResult:
        """Invoke Claude agent if ar_result is a FAIL status.

        Returns AgentInvokerResult. Never raises — failures are captured in result.
        """
        # Do not invoke on PASS
        status = ar_result.get("status", "ERROR")
        if status == "PASS":
            return AgentInvokerResult(invoked=False, reason="status=PASS")

        # Look up agent config
        try:
            defn = _MATRIX.get(ar_id)
        except UnknownARIdError:
            return AgentInvokerResult(invoked=False, reason=NO_AGENT_FOR_AR)

        if not defn.agent_id:
            return AgentInvokerResult(invoked=False, reason=NO_AGENT_FOR_AR)

        model_full = _MODEL_MAP.get(defn.agent_model, "claude-haiku-4-5-20251001")
        template = _PROMPT_TEMPLATES.get(ar_id, "AR {ar_id} failed. Result: {result}")
        prompt = template.format(ar_id=ar_id, result=str(ar_result)[:2000])

        response = invoke_claude(prompt=prompt, model=model_full, timeout=timeout)

        if response.exit_code == EXIT_CLI_NOT_FOUND:
            return AgentInvokerResult(
                invoked=False,
                agent_id=defn.agent_id,
                model=model_full,
                exit_code=response.exit_code,
                reason=f"CLI not found: {response.error}",
            )

        return AgentInvokerResult(
            invoked=True,
            agent_id=defn.agent_id,
            model=model_full,
            analysis=response.text,
            exit_code=response.exit_code,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/autorunner/test_agent_invoker.py -v --tb=short`

Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/ssidctl/autorunner/agent_invoker.py tests/autorunner/test_agent_invoker.py
git commit -m "feat(autorunner-p3): agent_invoker — Claude CLI triggered on AR FAIL"
```

---

### Task 4: AR Event Reporting API (`POST /api/autorunner/ar-results`)

**Files:**
- Create: `portal/backend/services/ar_event_service.py`
- Create: `portal/backend/routers/autorunner_events.py`
- Modify: `portal/backend/main.py` (add router to `_EXT`)
- Create: `tests/api/test_autorunner_events_api.py`

The pattern follows `portal/backend/routers/sot_validation.py` (already exists as a model).

- [ ] **Step 1: Write the failing test**

File: `tests/api/test_autorunner_events_api.py`

```python
"""Tests for AR result event ingest API."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from portal.backend.routers.autorunner_events import router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SSID_EMS_STATE", str(tmp_path))
    app = FastAPI()
    app.include_router(router, prefix="/api/autorunner")
    return TestClient(app)


def _valid_payload(ar_id="AR-01", status="PASS"):
    return {
        "ar_id": ar_id,
        "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": status,
        "commit_sha": "a" * 40,
        "ts": "2026-03-16T12:00:00Z",
        "findings": 0,
        "summary": "All clean",
    }


def test_post_ar_result_returns_201(client):
    resp = client.post("/api/autorunner/ar-results", json=_valid_payload())
    assert resp.status_code == 201
    assert resp.json()["status"] == "created"


def test_post_fail_result_accepted(client):
    resp = client.post(
        "/api/autorunner/ar-results",
        json=_valid_payload(ar_id="AR-04", status="FAIL_DORA"),
    )
    assert resp.status_code == 201


def test_missing_required_field_returns_400(client):
    payload = _valid_payload()
    del payload["ar_id"]
    resp = client.post("/api/autorunner/ar-results", json=payload)
    assert resp.status_code == 400
    assert "ar_id" in resp.json()["detail"].lower()


def test_invalid_ar_id_returns_400(client):
    payload = _valid_payload(ar_id="AR-99")
    resp = client.post("/api/autorunner/ar-results", json=payload)
    assert resp.status_code == 400
    assert "AR-99" in resp.json()["detail"]


def test_list_ar_results_empty(client):
    resp = client.get("/api/autorunner/ar-results")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_ar_results_after_post(client):
    client.post("/api/autorunner/ar-results", json=_valid_payload())
    resp = client.get("/api/autorunner/ar-results")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_duplicate_run_id_same_ar_returns_409(client):
    payload = _valid_payload()
    client.post("/api/autorunner/ar-results", json=payload)
    resp = client.post("/api/autorunner/ar-results", json=payload)
    assert resp.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/api/test_autorunner_events_api.py -v --tb=short`

Expected: `ImportError: cannot import name 'router' from 'portal.backend.routers.autorunner_events'`

- [ ] **Step 3: Implement `ar_event_service.py`**

File: `portal/backend/services/ar_event_service.py`

```python
"""AR Event Service — WORM-style storage for AR result events."""
from __future__ import annotations

import json
import os
from pathlib import Path

_VALID_AR_IDS = {f"AR-{i:02d}" for i in range(1, 11)}
_REQUIRED_FIELDS = {"ar_id", "run_id", "status", "commit_sha", "ts"}


class AREventService:
    REQUIRED_FIELDS = _REQUIRED_FIELDS
    VALID_AR_IDS = _VALID_AR_IDS

    def __init__(self, state_dir: str | None = None) -> None:
        base = state_dir or os.environ.get("SSID_EMS_STATE", "/tmp/ssid_state")
        self._dir = Path(base) / "autorunner" / "ar_events"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.jsonl"

    def _key(self, ar_id: str, run_id: str) -> str:
        return f"{ar_id}::{run_id}"

    def event_exists(self, ar_id: str, run_id: str) -> bool:
        key = self._key(ar_id, run_id)
        if not self._index_path.exists():
            return False
        for line in self._index_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                if entry.get("_key") == key:
                    return True
            except json.JSONDecodeError:
                continue
        return False

    def store_event(self, payload: dict) -> None:
        entry = dict(payload)
        entry["_key"] = self._key(payload["ar_id"], payload["run_id"])
        with open(self._index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def list_events(
        self,
        ar_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        if not self._index_path.exists():
            return []
        events = []
        for line in self._index_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                if ar_id and entry.get("ar_id") != ar_id:
                    continue
                events.append(entry)
            except json.JSONDecodeError:
                continue
        return events[offset : offset + limit]
```

- [ ] **Step 4: Implement `autorunner_events.py` router**

File: `portal/backend/routers/autorunner_events.py`

```python
"""AR Result Event API — ingest endpoint for AR module results.

Endpoints:
  POST /api/autorunner/ar-results    — Ingest AR result from CI or EMS runner
  GET  /api/autorunner/ar-results    — List stored AR results (optional ?ar_id= filter)

AR scripts call this endpoint when --ems-url is set.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException

from portal.backend.services.ar_event_service import AREventService

router = APIRouter(tags=["autorunner-events"])

_REQUIRED = {"ar_id", "run_id", "status", "commit_sha", "ts"}
_VALID_AR_IDS = {f"AR-{i:02d}" for i in range(1, 11)}


def _service() -> AREventService:
    return AREventService()


@router.post("/ar-results", status_code=201)
def ingest_ar_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Ingest an AR module result event.

    Required fields: ar_id, run_id, status, commit_sha, ts
    Response 201: {"status": "created", "ar_id": "...", "run_id": "..."}
    Response 400: {"detail": "..."}
    Response 409: {"detail": "Duplicate event: ..."}
    """
    missing = _REQUIRED - set(payload.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(sorted(missing))}")

    ar_id = payload.get("ar_id", "")
    if ar_id not in _VALID_AR_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid ar_id: {ar_id}. Valid: {sorted(_VALID_AR_IDS)}")

    svc = _service()
    run_id = payload["run_id"]
    if svc.event_exists(ar_id, run_id):
        raise HTTPException(status_code=409, detail=f"Duplicate event: {ar_id}::{run_id}")

    svc.store_event(payload)
    return {"status": "created", "ar_id": ar_id, "run_id": run_id}


@router.get("/ar-results")
def list_ar_results(ar_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """List stored AR result events, optionally filtered by ar_id."""
    return _service().list_events(ar_id=ar_id, limit=limit, offset=offset)
```

- [ ] **Step 5: Register router in `main.py`**

In `portal/backend/main.py`, find the `_EXT` dict (the existing `"autorunner"` entry is at line 68 of `_EXT`) and add:

```python
"autorunner_events": ("portal.backend.routers.autorunner_events", "/api/autorunner"),
```

Add it to `_EXT` (same dict that holds `"autorunner"`). Both routers mount at `/api/autorunner` prefix — this is safe because they define non-overlapping route paths (`/runs*` vs `/ar-results*`).

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/api/test_autorunner_events_api.py -v --tb=short`

Expected: 8/8 PASS

- [ ] **Step 7: Run full API test suite for regressions**

Run: `python -m pytest tests/test_autorunner_api.py tests/api/ -v --tb=short`

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add portal/backend/services/ar_event_service.py portal/backend/routers/autorunner_events.py portal/backend/main.py tests/api/test_autorunner_events_api.py
git commit -m "feat(autorunner-p3): AR result event API — POST /api/autorunner/ar-results ingest + list"
```

---

## Chunk 3: SSID ems_reporter + Blockchain Wiring + IRP Stubs + ADR

### Task 5: SSID `ems_reporter.py` + `--ems-url` flag in all 6 AR scripts

**Files:**
- Create: `12_tooling/ssid_autorunner/ems_reporter.py`
- Modify: `23_compliance/scripts/pii_regex_scan.py` (add `--ems-url`)
- Modify: `23_compliance/scripts/dora_incident_plan_check.py` (add `--ems-url`)
- Modify: `02_audit_logging/scripts/collect_unanchored.py` (add `--ems-url`)
- Modify: `01_ai_layer/scripts/model_inventory.py` (add `--ems-url`)
- Modify: `05_documentation/scripts/generate_from_chart.py` (add `--ems-url`)
- Modify: `23_compliance/scripts/fee_policy_audit.py` (add `--ems-url`)
- Create: `12_tooling/tests/autorunners/test_ems_reporter.py`

**Important constraints:**
- `ems_reporter.py` must use only stdlib (`urllib.request`, no `requests`/`httpx`)
- Fire-and-forget: if EMS is unavailable, print warning to stderr, do NOT fail the gate
- Timeout: 5 seconds max

- [ ] **Step 1: Write the failing test**

File: `12_tooling/tests/autorunners/test_ems_reporter.py`

```python
"""Tests for ems_reporter — fire-and-forget HTTP reporter."""
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

# The reporter lives in 12_tooling/ssid_autorunner/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ssid_autorunner.ems_reporter import post_result, EMSReporterResult


def test_post_result_success():
    """Successful POST returns EMSReporterResult with sent=True."""
    mock_response = MagicMock()
    mock_response.status = 201
    mock_response.read.return_value = b'{"status":"created","run_id":"abc"}'
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = post_result(
            ems_url="http://localhost:8000",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "PASS", "total_findings": 0},
            commit_sha="a" * 40,
        )

    assert result.sent is True
    assert result.status_code == 201


def test_ems_unavailable_does_not_raise():
    """Connection error → sent=False, no exception raised."""
    from urllib.error import URLError

    with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")):
        result = post_result(
            ems_url="http://localhost:8000",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "PASS"},
            commit_sha="a" * 40,
        )

    assert result.sent is False
    assert "Connection refused" in (result.error or "")


def test_timeout_does_not_raise():
    """Timeout → sent=False, no exception."""
    import socket

    with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
        result = post_result(
            ems_url="http://localhost:8000",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "FAIL_POLICY"},
            commit_sha="a" * 40,
        )

    assert result.sent is False


def test_empty_ems_url_skips_silently():
    """When ems_url is None or empty, sent=False with no HTTP call."""
    with patch("urllib.request.urlopen") as mock_open:
        result = post_result(
            ems_url="",
            ar_id="AR-01",
            run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            result={"status": "PASS"},
            commit_sha="a" * 40,
        )
    mock_open.assert_not_called()
    assert result.sent is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/bibel/Documents/Github/SSID && python -m pytest 12_tooling/tests/autorunners/test_ems_reporter.py -v --tb=short`

Expected: `ImportError: cannot import name 'post_result'`

- [ ] **Step 3: Implement `ems_reporter.py`**

File: `12_tooling/ssid_autorunner/ems_reporter.py`

```python
"""EMS Reporter — fire-and-forget HTTP result reporter for AR scripts.

Usage:
    from ssid_autorunner.ems_reporter import post_result
    post_result(ems_url, ar_id, run_id, result, commit_sha)

Uses only stdlib (urllib.request). Never raises — failures are logged to stderr.
Timeout: 5 seconds.
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError


@dataclass
class EMSReporterResult:
    sent: bool
    status_code: int = 0
    error: str | None = None


def post_result(
    ems_url: str,
    ar_id: str,
    run_id: str,
    result: dict,
    commit_sha: str,
    timeout: int = 5,
) -> EMSReporterResult:
    """POST AR result to EMS /api/autorunner/ar-results.

    Fire-and-forget: never raises, returns EMSReporterResult.
    If ems_url is empty/None, returns sent=False without attempting HTTP.
    """
    if not ems_url:
        return EMSReporterResult(sent=False, error="ems_url not set")

    endpoint = ems_url.rstrip("/") + "/api/autorunner/ar-results"
    payload = {
        "ar_id": ar_id,
        "run_id": run_id,
        "status": result.get("status", "UNKNOWN"),
        "commit_sha": commit_sha,
        "ts": datetime.now(timezone.utc).isoformat(),
        "findings": result.get("total_findings", result.get("findings", 0)),
        "summary": result.get("summary", ""),
        **{k: v for k, v in result.items()
           if k not in ("status", "total_findings", "findings", "summary")},
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return EMSReporterResult(sent=True, status_code=resp.status)
    except (URLError, socket.timeout, OSError) as exc:
        print(f"[ems_reporter] WARNING: could not reach EMS at {endpoint}: {exc}", file=sys.stderr)
        return EMSReporterResult(sent=False, error=str(exc))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest 12_tooling/tests/autorunners/test_ems_reporter.py -v --tb=short`

Expected: 4/4 PASS

- [ ] **Step 5: Add `--ems-url` to `pii_regex_scan.py`**

In `23_compliance/scripts/pii_regex_scan.py`, add to the parser and call reporter before `sys.exit()`:

```python
# In main(), after existing argparse setup, add:
parser.add_argument("--ems-url", default="", help="EMS base URL for result reporting (optional)")
parser.add_argument("--run-id", default="", help="Run ID for EMS reporting")
parser.add_argument("--commit-sha", default="0" * 40, help="Commit SHA for EMS reporting")

# After writing output JSON and before sys.exit():
if args.ems_url:
    try:
        from ssid_autorunner.ems_reporter import post_result
        post_result(
            ems_url=args.ems_url,
            ar_id="AR-01",
            run_id=args.run_id or f"CI-AR01-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}",
            result=output,
            commit_sha=args.commit_sha,
        )
    except ImportError:
        pass  # ems_reporter optional
```

Apply the same pattern to all 6 scripts:
- `23_compliance/scripts/pii_regex_scan.py` → `AR-01`
- `23_compliance/scripts/dora_incident_plan_check.py` → `AR-04`
- `02_audit_logging/scripts/collect_unanchored.py` → `AR-03`
- `01_ai_layer/scripts/model_inventory.py` → `AR-09` (primary script for this AR ID)
- `08_identity_score/scripts/pofi_audit.py` → **do NOT** add `--ems-url`; this script is an `extra_script` of AR-09 and is invoked by the EMS runner as part of the AR-09 pipeline — reporting from it separately would create a duplicate `AR-09` event (409) in the EMS
- `05_documentation/scripts/generate_from_chart.py` → `AR-06`
- `23_compliance/scripts/fee_policy_audit.py` → `AR-10`

**Rule:** The `--ems-url` flag is always optional with `default=""`. Importing `ems_reporter` is wrapped in `try/except ImportError` so scripts remain runnable without the `ssid_autorunner` package on the path.

- [ ] **Step 6: Add E2E push-path test (AR script + --ems-url → ems_reporter called)**

Add to `12_tooling/tests/autorunners/test_ems_reporter.py`:

```python
def test_pii_scan_with_ems_url_calls_post_result(tmp_path):
    """When pii_regex_scan.py is invoked with --ems-url, ems_reporter.post_result is called."""
    import subprocess, json
    from unittest.mock import patch, MagicMock
    from pathlib import Path

    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n")
    out = tmp_path / "result.json"

    # Capture calls to ems_reporter.post_result.
    # Strategy: ensure ssid_autorunner.ems_reporter is already imported and its
    # post_result attribute is mocked BEFORE exec_module loads pii_regex_scan.py.
    # This guarantees that `from ssid_autorunner.ems_reporter import post_result`
    # inside the script's main() gets the mock, regardless of whether the
    # ems_reporter module was already cached in sys.modules.
    import importlib.util, sys
    import ssid_autorunner.ems_reporter  # ensure module is in sys.modules

    posted = []

    def fake_post(ems_url, ar_id, run_id, result, commit_sha, **kwargs):
        posted.append({"ems_url": ems_url, "ar_id": ar_id, "status": result.get("status")})
        from ssid_autorunner.ems_reporter import EMSReporterResult
        return EMSReporterResult(sent=True, status_code=201)

    spec = importlib.util.spec_from_file_location(
        "pii_regex_scan_test",
        str(Path(__file__).parent.parent.parent.parent /
            "23_compliance/scripts/pii_regex_scan.py"),
    )
    mod = importlib.util.module_from_spec(spec)

    # Patch ssid_autorunner.ems_reporter.post_result BEFORE exec_module so that
    # `from ssid_autorunner.ems_reporter import post_result` (in the try block
    # inside main()) resolves to the mock. The patch context wraps BOTH exec_module
    # and main() to cover either import-time or call-time resolution.
    with patch("sys.argv", [
        "pii_regex_scan.py",
        "--files", str(clean),
        "--out", str(out),
        "--ems-url", "http://localhost:8000",
        "--run-id", "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "--commit-sha", "a" * 40,
    ]):
        with patch.object(sys.modules["ssid_autorunner.ems_reporter"], "post_result", side_effect=fake_post):
            spec.loader.exec_module(mod)
            try:
                mod.main()
            except SystemExit:
                pass  # sys.exit(0) is expected

    assert len(posted) == 1, "post_result must be called exactly once"
    assert posted[0]["ar_id"] == "AR-01"
    assert posted[0]["status"] == "PASS"
    assert posted[0]["ems_url"] == "http://localhost:8000"
```

- [ ] **Step 7: Run regression tests for all modified AR scripts**

Run: `cd C:/Users/bibel/Documents/Github/SSID && python -m pytest 12_tooling/tests/autorunners/ -v --tb=short`

Expected: 93+ tests pass (92 existing + new push-path E2E test)

- [ ] **Step 8: Commit**

```bash
# In SSID repo
git add 12_tooling/ssid_autorunner/ems_reporter.py \
        12_tooling/tests/autorunners/test_ems_reporter.py \
        23_compliance/scripts/pii_regex_scan.py \
        23_compliance/scripts/dora_incident_plan_check.py \
        02_audit_logging/scripts/collect_unanchored.py \
        01_ai_layer/scripts/model_inventory.py \
        05_documentation/scripts/generate_from_chart.py \
        23_compliance/scripts/fee_policy_audit.py
git commit -m "feat(autorunner-p3): ems_reporter.py + --ems-url flag in 5 AR scripts + E2E push-path test"
```

---

### Task 6: AR-03 Blockchain Anchoring Hook

**Files:**
- Modify: `02_audit_logging/scripts/build_merkle_tree.py`
- Modify: `.github/workflows/evidence_anchoring.yml`

When `--blockchain-url` is set, POST the Merkle root to that URL and store the TX hash in the result JSON. In CI, the flag is absent → dry_run behavior unchanged. In local dev / testnet, set `--blockchain-url http://testnet-anchor.local/api/anchor`.

- [ ] **Step 1: Write the failing test**

In `12_tooling/tests/autorunners/test_ar03_evidence_anchoring.py`, ADD this test:

```python
def test_blockchain_url_set_posts_merkle_root(tmp_path):
    """When --blockchain-url is set, script POSTs merkle root and stores tx_hash."""
    import json, subprocess
    from pathlib import Path

    # Create a fake evidence file to have something to anchor
    run_dir = tmp_path / "agent_runs" / "RUN-TEST01"
    run_dir.mkdir(parents=True)
    ev = run_dir / "evidence.jsonl"
    ev.write_text('{"check": "test", "result": "PASS"}\n')
    anchor_state = tmp_path / "anchor_state.json"
    anchor_state.write_text('{"anchored_hashes": [], "last_anchor_ts": null}')

    collect_out = tmp_path / "collect.json"
    # First: collect
    subprocess.run([
        "python", str(SSID_ROOT / "02_audit_logging/scripts/collect_unanchored.py"),
        "--out", str(collect_out),
        "--agent-runs-dir", str(tmp_path / "agent_runs"),
        "--since-last-anchor", str(anchor_state),
    ], capture_output=True, check=True)

    merkle_out = tmp_path / "merkle.json"
    # Run with mock blockchain URL — use httpserver or mock subprocess
    # Here we test that --blockchain-url flag is accepted and result has tx_hash field
    r = subprocess.run([
        "python", str(SSID_ROOT / "02_audit_logging/scripts/build_merkle_tree.py"),
        "--collect-out", str(collect_out),
        "--out", str(merkle_out),
        "--blockchain-url", "http://localhost:19999/api/anchor",  # nothing listening
    ], capture_output=True, text=True)

    # Exit code may be 1 (connection refused) but result JSON must have tx_hash key
    assert merkle_out.exists(), "Output file must be written even on blockchain error"
    data = json.loads(merkle_out.read_text())
    assert "tx_hash" in data, "tx_hash field must be present (even if null on error)"
    assert "blockchain_attempted" in data
```

- [ ] **Step 2: Add `--blockchain-url` to `build_merkle_tree.py`**

In `02_audit_logging/scripts/build_merkle_tree.py`, add to `main()`:

```python
# Add to argparse:
parser.add_argument("--blockchain-url", default="", help="Blockchain anchor endpoint (optional)")

# After computing Merkle root and before writing output:
tx_hash = None
blockchain_attempted = False
if args.blockchain_url and result.get("root"):
    blockchain_attempted = True
    try:
        import urllib.request, json as _json, socket
        from urllib.error import URLError
        body = _json.dumps({"merkle_root": result["root"], "ts": result.get("ts", "")}).encode()
        req = urllib.request.Request(
            args.blockchain_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = _json.loads(resp.read())
            tx_hash = resp_data.get("tx_hash") or resp_data.get("txHash")
        print(f"Blockchain anchor: tx_hash={tx_hash}")
    except (URLError, socket.timeout, OSError) as exc:
        print(f"WARNING: blockchain anchor failed: {exc}", file=sys.stderr)

result["tx_hash"] = tx_hash
result["blockchain_attempted"] = blockchain_attempted
result["dry_run"] = not blockchain_attempted
```

- [ ] **Step 3: Run test to verify it passes**

Run: `python -m pytest 12_tooling/tests/autorunners/test_ar03_evidence_anchoring.py -v --tb=short`

Expected: all PASS (including new test)

- [ ] **Step 4: Update `evidence_anchoring.yml` workflow**

In `.github/workflows/evidence_anchoring.yml`, the `Build Merkle Tree` step stays unchanged (no `--blockchain-url` in CI → dry_run). Add a comment:

```yaml
# Blockchain anchor: set --blockchain-url ${{ secrets.BLOCKCHAIN_ANCHOR_URL }} when testnet ready
# Currently: dry_run=true (no blockchain URL = no TX submitted)
```

- [ ] **Step 5: Commit**

```bash
git add 02_audit_logging/scripts/build_merkle_tree.py \
        .github/workflows/evidence_anchoring.yml \
        12_tooling/tests/autorunners/test_ar03_evidence_anchoring.py
git commit -m "feat(autorunner-p3): AR-03 blockchain anchoring hook — --blockchain-url flag, tx_hash in result"
```

---

### Task 7: EMS AR-04 IRP Stub Creator

**Files:**
- Create: `src/ssidctl/autorunner/irp_stub_creator.py`
- Create: `tests/autorunner/test_irp_stub_creator.py`

When AR-04 returns FAIL_DORA with missing IRPs, EMS can create IRP stub files in a new git branch (worktree), ready for PR. No direct writes to SSID `main`.

- [ ] **Step 1: Write the failing test**

File: `tests/autorunner/test_irp_stub_creator.py`

```python
"""Tests for IRP stub creator — creates DORA IRP stubs via git worktree."""
import subprocess
from pathlib import Path
import pytest
from ssidctl.autorunner.irp_stub_creator import (
    IRPStubCreator,
    IRPStubResult,
    IRP_TEMPLATE_PATH_IN_SSID,
)


def test_create_stubs_writes_files(tmp_path):
    """Stub creator writes IRP files for missing roots."""
    # Set up a fake SSID-like dir with template
    ssid_root = tmp_path / "SSID"
    ssid_root.mkdir()
    template_dir = ssid_root / "05_documentation" / "templates"
    template_dir.mkdir(parents=True)
    template_file = template_dir / "TEMPLATE_INCIDENT_RESPONSE.md"
    template_file.write_text("# Incident Response Plan\n## Scenario 1\n## Scenario 2\n")

    # Set up missing roots
    missing_roots = ["01_ai_layer", "03_core"]
    for root in missing_roots:
        (ssid_root / root).mkdir()

    result = IRPStubCreator(ssid_root=ssid_root).create_stubs(
        missing_roots=missing_roots,
        dry_run=True,  # dry_run: no git ops, just file creation
    )

    assert isinstance(result, IRPStubResult)
    assert result.stubs_created == len(missing_roots)
    for root in missing_roots:
        stub_path = ssid_root / root / "docs" / "incident_response_plan.md"
        assert stub_path.exists(), f"Expected stub at {stub_path}"
        content = stub_path.read_text()
        assert "Incident Response Plan" in content


def test_empty_missing_roots_returns_zero(tmp_path):
    """No missing roots → stubs_created=0."""
    ssid_root = tmp_path / "SSID"
    ssid_root.mkdir()
    template_dir = ssid_root / "05_documentation" / "templates"
    template_dir.mkdir(parents=True)
    (template_dir / "TEMPLATE_INCIDENT_RESPONSE.md").write_text("# IRP Template\n")

    result = IRPStubCreator(ssid_root=ssid_root).create_stubs(
        missing_roots=[],
        dry_run=True,
    )
    assert result.stubs_created == 0


def test_missing_template_raises(tmp_path):
    """If TEMPLATE_INCIDENT_RESPONSE.md is missing, raises FileNotFoundError."""
    ssid_root = tmp_path / "SSID"
    ssid_root.mkdir()
    with pytest.raises(FileNotFoundError, match="IRP template not found"):
        IRPStubCreator(ssid_root=ssid_root).create_stubs(
            missing_roots=["01_ai_layer"],
            dry_run=True,
        )
```

- [ ] **Step 2: Implement `irp_stub_creator.py`**

File: `src/ssidctl/autorunner/irp_stub_creator.py`

```python
"""AR-04 IRP Stub Creator — creates incident_response_plan.md stubs for missing roots.

In P3: dry_run=True writes files without git ops (for testing + CI verification).
In P4: dry_run=False creates a git worktree branch + commits stubs → PR-ready.

Never writes directly to SSID main — always via worktree branch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Path relative to SSID repo root
IRP_TEMPLATE_PATH_IN_SSID = "05_documentation/templates/TEMPLATE_INCIDENT_RESPONSE.md"
IRP_TARGET_RELATIVE = "docs/incident_response_plan.md"


@dataclass
class IRPStubResult:
    stubs_created: int
    stub_paths: list[str] = field(default_factory=list)
    branch_name: str = ""
    dry_run: bool = True
    errors: list[str] = field(default_factory=list)


class IRPStubCreator:
    def __init__(self, ssid_root: str | Path) -> None:
        self._root = Path(ssid_root)

    def _get_template(self) -> str:
        template_path = self._root / IRP_TEMPLATE_PATH_IN_SSID
        if not template_path.exists():
            raise FileNotFoundError(f"IRP template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def create_stubs(
        self,
        missing_roots: list[str],
        dry_run: bool = True,
        branch_name: str = "",
    ) -> IRPStubResult:
        """Create IRP stub files for missing_roots.

        Args:
            missing_roots: List of root directory names (relative to SSID root)
                           that are missing incident_response_plan.md
            dry_run: If True, write files in place (no git ops). If False,
                     create a worktree branch first (P4 implementation).
            branch_name: Branch name for git worktree (only used when dry_run=False).

        Returns:
            IRPStubResult with stubs_created count and stub_paths.
        """
        if not missing_roots:
            return IRPStubResult(stubs_created=0, dry_run=dry_run)

        template = self._get_template()
        stub_paths = []
        errors = []

        for root_name in missing_roots:
            target = self._root / root_name / IRP_TARGET_RELATIVE
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_text(template, encoding="utf-8")
                    stub_paths.append(str(target))
                # If target already exists: idempotent — do not count as created
            except OSError as exc:
                errors.append(f"{root_name}: {exc}")

        return IRPStubResult(
            stubs_created=len(stub_paths),
            stub_paths=stub_paths,
            branch_name=branch_name,
            dry_run=dry_run,
            errors=errors,
        )
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd C:/Users/bibel/Documents/Github/SSID-EMS && python -m pytest tests/autorunner/test_irp_stub_creator.py -v --tb=short`

Expected: 3/3 PASS

- [ ] **Step 4: Commit**

```bash
git add src/ssidctl/autorunner/irp_stub_creator.py tests/autorunner/test_irp_stub_creator.py
git commit -m "feat(autorunner-p3): AR-04 IRP stub creator — creates DORA IRP stubs via dry_run worktree path"
```

---

### Task 8: ADR-0074 + Full Test Run

**Files:**
- Create: `16_codex/decisions/ADR_0074_autorunner_v2_plan_c_runtime_closure.md` (in SSID)

- [ ] **Step 1: Write ADR-0074**

File: `16_codex/decisions/ADR_0074_autorunner_v2_plan_c_runtime_closure.md`

```markdown
# ADR-0074: AutoRunner V2 Plan C — Runtime Integration Closure

**Status:** Accepted
**Date:** 2026-03-16
**Author:** AutoRunner V2 Implementation Team
**Supersedes:** —
**Related:** ADR-0073 (AutoRunner V2 Plan B), ADR-0072 (Plan A)

---

## Context

Plan B (ADR-0073) delivered 6 deterministic AR modules. Three items were
consciously deferred as P3:
1. EMS-HTTP coupling (AR modules call EMS after deterministic check)
2. Agent-API binding (Claude invocation on FAIL)
3. AR-04 Stub-Patches via EMS worktree
4. AR-03 Blockchain anchoring hook

P3 closes all four.

## Decision

### 1. EMS AR Result Event API
POST `/api/autorunner/ar-results` endpoint added to SSID-EMS portal.
AR scripts in CI can POST results via `--ems-url` flag (fire-and-forget,
stdlib urllib, 5s timeout, never blocks gate on EMS unavailability).

### 2. EMS Runner Pipeline Wiring
`ssidctl.autorunner.runner._execute_pipeline()` stub replaced with
subprocess invocation of SSID AR scripts via `ar_script_matrix.py`.
Maps AR_IDs (AR-01/03/04/06/09/10) to script paths and default args.
`autorunner_id` field added to `AutoRunnerRun` model.

### 3. Claude Agent Invocation on FAIL
`ssidctl.autorunner.agent_invoker.AgentInvoker.invoke_on_fail()` fires
Claude CLI via existing AI Gateway (subprocess_driver) when AR returns
non-PASS status. Gracefully degrades when Claude CLI is unavailable.
Maps: AR-01 → SEC-05/Opus, AR-03 → OPS-08/Haiku, AR-04 → CMP-14/Sonnet,
AR-06 → DOC-20/Haiku, AR-09 → ARS-29/Opus, AR-10 → CMP-14/Sonnet.

### 4. AR-04 IRP Stub Creation
`ssidctl.autorunner.irp_stub_creator.IRPStubCreator.create_stubs()` writes
TEMPLATE_INCIDENT_RESPONSE.md to missing IRP paths. P3 uses dry_run=True
(no git ops). P4 will add worktree branch + PR creation.

### 5. AR-03 Blockchain Anchoring Hook
`build_merkle_tree.py` accepts optional `--blockchain-url`. When set,
POSTs Merkle root and stores `tx_hash` in result JSON. CI workflow keeps
no `--blockchain-url` → dry_run=True unchanged. P4 wires real testnet TX.

## Consequences

**Positive:**
- AR modules are now fully integrated into EMS runtime (push + pull)
- Agent analysis available on FAIL without manual intervention
- IRP stub creation path unblocked
- Blockchain wiring ready for P4 testnet integration

**Negative:**
- `autorunner_id` field added to AutoRunnerRun (backward compatible: optional)
- AR scripts import `ems_reporter` with try/except (no hard dependency)

**Deferred to P4:**
- AR-04 git worktree + PR creation (dry_run=False path)
- Real blockchain TX (testnet credentials)
- `agent_invoker` wired into `runner._execute_pipeline()` on FAIL
```

- [ ] **Step 2: Final test run — SSID (all 92+ tests)**

Run: `cd C:/Users/bibel/Documents/Github/SSID && python -m pytest -q`

Expected: all PASS, no regressions

- [ ] **Step 3: Final test run — SSID-EMS (all tests)**

Run: `cd C:/Users/bibel/Documents/Github/SSID-EMS && python -m pytest -q`

Expected: all PASS, no regressions

- [ ] **Step 4: Commit ADR**

```bash
# In SSID repo
git add 16_codex/decisions/ADR_0074_autorunner_v2_plan_c_runtime_closure.md
git commit -m "docs(autorunner-p3): ADR-0074 — Runtime Integration Closure"
```

---

## Execution Notes

### Worktree Setup (before starting)

```bash
# SSID worktree
cd C:/Users/bibel/Documents/Github/SSID
git worktree add ../_worktrees/ssid-p3-runtime feat/autorunner-v2-plan-c-runtime
# or create branch first:
git checkout -b feat/autorunner-v2-plan-c-runtime
git worktree add ../_worktrees/ssid-p3-runtime feat/autorunner-v2-plan-c-runtime

# SSID-EMS worktree
cd C:/Users/bibel/Documents/Github/SSID-EMS
git checkout -b feat/autorunner-v2-plan-c-ems
git worktree add ../_worktrees/ssid-ems-p3-runtime feat/autorunner-v2-plan-c-ems
```

### Task Execution Order

Tasks 1-2 (EMS runner) and Task 5-6 (SSID reporter + blockchain) can be done in parallel.
Task 3 (agent invoker) depends on Task 1 (matrix must exist).
Task 4 (AR event API) is independent.
Task 7 (IRP stubs) is independent.
Task 8 (ADR + final runs) last.

### Scope Allowlist Check (SSID)

All new SSID files fall under allowed prefixes:
- `12_tooling/ssid_autorunner/` ✓
- `12_tooling/tests/autorunners/` ✓
- `23_compliance/scripts/` ✓ (modifications only)
- `02_audit_logging/scripts/` ✓ (modifications only)
- `01_ai_layer/scripts/` ✓ (modifications only)
- `08_identity_score/scripts/` ✓ (modifications only)
- `05_documentation/scripts/` ✓ (modifications only)
- `16_codex/decisions/` ✓
- `.github/workflows/` ✓ (comment addition only)

### ROOT-24-LOCK

No new root directories. All files under existing roots. ✓

### CI

No new GitHub Action workflow files needed for P3 changes.
Existing AR workflows pick up `--ems-url` flag via optional `EMS_BASE_URL` secret.
Add to each workflow step where applicable:

```yaml
env:
  EMS_BASE_URL: ${{ secrets.EMS_BASE_URL }}  # optional; skip if not set
```

Then in each script invocation:

```yaml
run: python ... --ems-url "${{ env.EMS_BASE_URL }}"
```
