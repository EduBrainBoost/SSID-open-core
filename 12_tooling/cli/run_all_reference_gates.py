#!/usr/bin/env python3
"""Convergence Orchestrator — CC-SSID-SOT-CONVERGENCE-01.

Runs all 4 SoT/reference gates in fixed sequence and produces a unified
convergence report (JSON + Markdown).

Execution order (fixed):
  1. SoT Validator        (subprocess — no public Python API)
  2. Cross-Artifact Ref   (cross_artifact_reference_audit.run_audit)
  3. Sync Guard           (sot_sync_guard.run_guard)
  4. Baseline Gate        (sot_baseline_gate evaluation pipeline)

Exit codes:
  0 = PASS or WARN (all gates passed or only warnings)
  2 = FAIL         (at least one gate FAIL or fail-closed condition)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure sibling imports work
# ---------------------------------------------------------------------------
_cli_dir = str(Path(__file__).resolve().parent)
if _cli_dir not in sys.path:
    sys.path.insert(0, _cli_dir)

from cross_artifact_reference_audit import (  # noqa: E402
    SOT_ARTIFACTS,
    AuditResult,
    Finding,
)
from cross_artifact_reference_audit import (
    generate_report as _xref_generate_report,
)
from cross_artifact_reference_audit import (
    run_audit as _xref_run_audit,
)
from sot_baseline_gate import (  # noqa: E402
    DEFAULT_BASELINE_REL,
    DEFAULT_INTENT_REL,
    DEFAULT_OUTPUT_REL,
    compare_workspace_to_baseline,
    evaluate_baseline_gate,
    load_baseline_snapshot,
    load_change_intent,
)
from sot_baseline_gate import (
    build_report_dict as _baseline_build_report_dict,
)
from sot_baseline_gate import (
    emit_reports as _baseline_emit_reports,
)
from sot_sync_guard import (
    generate_report as _sync_generate_report,
)
from sot_sync_guard import (  # noqa: E402
    run_guard as _sync_run_guard,
)

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2

# Gate IDs (execution order)
GATE_SOT_VALIDATOR = "sot_validator"
GATE_XREF_AUDIT = "xref_audit"
GATE_SYNC_GUARD = "sync_guard"
GATE_BASELINE_GATE = "baseline_gate"

GATE_ORDER = [
    GATE_SOT_VALIDATOR,
    GATE_XREF_AUDIT,
    GATE_SYNC_GUARD,
    GATE_BASELINE_GATE,
]

GATE_NAMES = {
    GATE_SOT_VALIDATOR: "SoT Validator",
    GATE_XREF_AUDIT: "Cross-Artifact Reference Audit",
    GATE_SYNC_GUARD: "SoT Sync Guard",
    GATE_BASELINE_GATE: "SoT Baseline Gate",
}

CONVERGENCE_REPORT_JSON = "reference_gates_convergence_report.json"
CONVERGENCE_REPORT_MD = "reference_gates_convergence_report.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(obj: Any) -> str:
    """SHA-256 of JSON-serialised object (same pattern as sot_baseline_gate)."""
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _detect_repo_root() -> Path:
    """Auto-detect repo root from script location (two levels up from 12_tooling/cli/)."""
    return Path(__file__).resolve().parents[2]


def _decision_from_exit_code(exit_code: int) -> str:
    if exit_code == 0:
        return "PASS"
    if exit_code == 1:
        return "WARN"
    if exit_code == 2:
        return "FAIL"
    return "FAIL"  # unexpected → fail-closed


# ---------------------------------------------------------------------------
# GateResult dataclass
# ---------------------------------------------------------------------------
@dataclass
class GateResult:
    gate_id: str
    gate_name: str
    decision: str  # PASS | WARN | FAIL
    exit_code: int
    duration_ms: int
    findings_total: int
    findings_deny: int
    findings_warn: int
    artifacts_checked: int
    report_path_json: str | None
    report_path_md: str | None
    evidence_hash: str
    started_at_utc: str
    finished_at_utc: str


# ---------------------------------------------------------------------------
# Individual gate runners
# ---------------------------------------------------------------------------
def run_sot_validator(repo: Path, timeout_seconds: int | None = None) -> GateResult:
    """Run sot_validator.py --verify-all as subprocess."""
    gate_id = GATE_SOT_VALIDATOR
    gate_name = GATE_NAMES[gate_id]
    started = _utc_now_iso()
    t0 = time.monotonic()

    findings_dicts: list[dict] = []
    exit_code = 2
    artifacts_checked = len(SOT_ARTIFACTS)

    try:
        validator_script = Path(__file__).resolve().parent / "sot_validator.py"
        if not validator_script.exists():
            findings_dicts.append(
                Finding(
                    "gate_execution_failed",
                    "deny",
                    str(validator_script),
                    "sot_validator.py not found on disk",
                ).to_dict()
            )
            raise FileNotFoundError(str(validator_script))

        timeout = timeout_seconds if timeout_seconds else 120
        proc = subprocess.run(
            [sys.executable, str(validator_script), "--verify-all"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code = proc.returncode

        # Parse stdout for violation details
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        if exit_code == 2:
            # Extract violation lines
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith("VIOLATIONS:"):
                    rule_ids = line.replace("VIOLATIONS:", "").strip()
                    for rid in rule_ids.split(","):
                        rid = rid.strip()
                        if rid:
                            findings_dicts.append(
                                {
                                    "class": "sot_validation_failure",
                                    "severity": "deny",
                                    "path": "sot_validator",
                                    "detail": f"rule '{rid}' failed validation",
                                }
                            )
                elif line.startswith("INTERFEDERATION-SPEC-ONLY:"):
                    findings_dicts.append(
                        {
                            "class": "interfederation_path_violation",
                            "severity": "deny",
                            "path": "sot_validator",
                            "detail": line,
                        }
                    )
            if not findings_dicts:
                findings_dicts.append(
                    {
                        "class": "sot_validation_failure",
                        "severity": "deny",
                        "path": "sot_validator",
                        "detail": f"exit code 2; stdout: {stdout[:500]}",
                    }
                )
        elif exit_code not in (0, 1, 2):
            findings_dicts.append(
                {
                    "class": "gate_exitcode_unexpected",
                    "severity": "deny",
                    "path": "sot_validator",
                    "detail": f"unexpected exit code {exit_code}; stderr: {stderr[:500]}",
                }
            )
            exit_code = 2  # fail-closed

    except subprocess.TimeoutExpired:
        findings_dicts.append(
            {
                "class": "gate_timeout",
                "severity": "deny",
                "path": "sot_validator",
                "detail": f"sot_validator timed out after {timeout_seconds}s",
            }
        )
        exit_code = 2
    except FileNotFoundError:
        exit_code = 2
    except Exception as exc:
        findings_dicts.append(
            {
                "class": "gate_execution_failed",
                "severity": "deny",
                "path": "sot_validator",
                "detail": f"unexpected error: {exc}",
            }
        )
        exit_code = 2

    t1 = time.monotonic()
    finished = _utc_now_iso()
    duration_ms = int((t1 - t0) * 1000)
    evidence_hash = _json_sha256(findings_dicts)

    deny_count = sum(1 for f in findings_dicts if f.get("severity") == "deny")
    warn_count = sum(1 for f in findings_dicts if f.get("severity") == "warn")

    return GateResult(
        gate_id=gate_id,
        gate_name=gate_name,
        decision=_decision_from_exit_code(exit_code),
        exit_code=exit_code,
        duration_ms=duration_ms,
        findings_total=len(findings_dicts),
        findings_deny=deny_count,
        findings_warn=warn_count,
        artifacts_checked=artifacts_checked,
        report_path_json=None,
        report_path_md=None,
        evidence_hash=evidence_hash,
        started_at_utc=started,
        finished_at_utc=finished,
    )


def run_reference_audit(repo: Path) -> GateResult:
    """Run cross_artifact_reference_audit.run_audit()."""
    gate_id = GATE_XREF_AUDIT
    gate_name = GATE_NAMES[gate_id]
    started = _utc_now_iso()
    t0 = time.monotonic()

    findings_dicts: list[dict] = []
    exit_code = 2
    report_path_json: str | None = None
    report_path_md: str | None = None
    artifacts_checked = len(SOT_ARTIFACTS)

    try:
        result = _xref_run_audit(repo)
        report = _xref_generate_report(result, repo)

        findings_dicts = [f.to_dict() for f in result.findings]
        exit_code = result.exit_code

        # Write report
        output_dir = repo / "02_audit_logging" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "cross_artifact_reference_audit_report.json"
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        report_path_json = str(json_path)

    except Exception as exc:
        findings_dicts.append(
            {
                "class": "gate_execution_failed",
                "severity": "deny",
                "path": "cross_artifact_reference_audit",
                "detail": f"unexpected error: {exc}",
            }
        )
        exit_code = 2

    t1 = time.monotonic()
    finished = _utc_now_iso()
    duration_ms = int((t1 - t0) * 1000)
    evidence_hash = _json_sha256(findings_dicts)

    deny_count = sum(1 for f in findings_dicts if f.get("severity") == "deny")
    warn_count = sum(1 for f in findings_dicts if f.get("severity") == "warn")

    return GateResult(
        gate_id=gate_id,
        gate_name=gate_name,
        decision=_decision_from_exit_code(exit_code),
        exit_code=exit_code,
        duration_ms=duration_ms,
        findings_total=len(findings_dicts),
        findings_deny=deny_count,
        findings_warn=warn_count,
        artifacts_checked=artifacts_checked,
        report_path_json=report_path_json,
        report_path_md=report_path_md,
        evidence_hash=evidence_hash,
        started_at_utc=started,
        finished_at_utc=finished,
    )


def run_sync_guard(repo: Path) -> GateResult:
    """Run sot_sync_guard.run_guard() with no changed_files (full check)."""
    gate_id = GATE_SYNC_GUARD
    gate_name = GATE_NAMES[gate_id]
    started = _utc_now_iso()
    t0 = time.monotonic()

    findings_dicts: list[dict] = []
    exit_code = 2
    report_path_json: str | None = None
    report_path_md: str | None = None
    artifacts_checked = len(SOT_ARTIFACTS)

    try:
        result, changed_keys, affected_keys, sync_plan = _sync_run_guard(repo)
        report = _sync_generate_report(result, repo, changed_keys, affected_keys, sync_plan)

        findings_dicts = [f.to_dict() for f in result.findings]
        exit_code = result.exit_code

        # Write report
        output_dir = repo / "02_audit_logging" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "sot_sync_guard_report.json"
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        report_path_json = str(json_path)

    except Exception as exc:
        findings_dicts.append(
            {
                "class": "gate_execution_failed",
                "severity": "deny",
                "path": "sot_sync_guard",
                "detail": f"unexpected error: {exc}",
            }
        )
        exit_code = 2

    t1 = time.monotonic()
    finished = _utc_now_iso()
    duration_ms = int((t1 - t0) * 1000)
    evidence_hash = _json_sha256(findings_dicts)

    deny_count = sum(1 for f in findings_dicts if f.get("severity") == "deny")
    warn_count = sum(1 for f in findings_dicts if f.get("severity") == "warn")

    return GateResult(
        gate_id=gate_id,
        gate_name=gate_name,
        decision=_decision_from_exit_code(exit_code),
        exit_code=exit_code,
        duration_ms=duration_ms,
        findings_total=len(findings_dicts),
        findings_deny=deny_count,
        findings_warn=warn_count,
        artifacts_checked=artifacts_checked,
        report_path_json=report_path_json,
        report_path_md=report_path_md,
        evidence_hash=evidence_hash,
        started_at_utc=started,
        finished_at_utc=finished,
    )


def run_baseline_gate(repo: Path) -> GateResult:
    """Run sot_baseline_gate evaluation pipeline."""
    gate_id = GATE_BASELINE_GATE
    gate_name = GATE_NAMES[gate_id]
    started = _utc_now_iso()
    t0 = time.monotonic()

    findings_dicts: list[dict] = []
    exit_code = 2
    report_path_json: str | None = None
    report_path_md: str | None = None
    artifacts_checked = len(SOT_ARTIFACTS)

    try:
        baseline_path = repo / DEFAULT_BASELINE_REL
        intent_path = repo / DEFAULT_INTENT_REL
        output_dir = repo / DEFAULT_OUTPUT_REL

        result = AuditResult()
        baseline = load_baseline_snapshot(baseline_path)
        intent = load_change_intent(intent_path)

        changed_artifacts: list[dict] = []
        if baseline is not None:
            comparison_result, changed_artifacts = compare_workspace_to_baseline(repo, baseline)
            for f in comparison_result.findings:
                result.add(f)

        decision = evaluate_baseline_gate(repo, baseline, intent, changed_artifacts, result)

        report = _baseline_build_report_dict(repo, decision, baseline, intent, changed_artifacts, result)

        _baseline_emit_reports(report, output_dir)

        findings_dicts = [f.to_dict() for f in result.findings]

        if decision == "FAIL":
            exit_code = 2
        elif decision == "WARN":
            exit_code = 1
        else:
            exit_code = 0

        json_path = output_dir / "sot_baseline_gate_report.json"
        md_path = output_dir / "sot_baseline_gate_report.md"
        report_path_json = str(json_path) if json_path.exists() else None
        report_path_md = str(md_path) if md_path.exists() else None

    except Exception as exc:
        findings_dicts.append(
            {
                "class": "gate_execution_failed",
                "severity": "deny",
                "path": "sot_baseline_gate",
                "detail": f"unexpected error: {exc}",
            }
        )
        exit_code = 2

    t1 = time.monotonic()
    finished = _utc_now_iso()
    duration_ms = int((t1 - t0) * 1000)
    evidence_hash = _json_sha256(findings_dicts)

    deny_count = sum(1 for f in findings_dicts if f.get("severity") == "deny")
    warn_count = sum(1 for f in findings_dicts if f.get("severity") == "warn")

    return GateResult(
        gate_id=gate_id,
        gate_name=gate_name,
        decision=_decision_from_exit_code(exit_code),
        exit_code=exit_code,
        duration_ms=duration_ms,
        findings_total=len(findings_dicts),
        findings_deny=deny_count,
        findings_warn=warn_count,
        artifacts_checked=artifacts_checked,
        report_path_json=report_path_json,
        report_path_md=report_path_md,
        evidence_hash=evidence_hash,
        started_at_utc=started,
        finished_at_utc=finished,
    )


# ---------------------------------------------------------------------------
# Normalise / aggregate / decide
# ---------------------------------------------------------------------------
def normalize_gate_result(
    gate_id: str,
    gate_name: str,
    exit_code: int,
    findings_dicts: list[dict],
    duration_ms: int,
    artifacts_checked: int,
    report_paths: dict[str, str | None],
    evidence_hash: str,
) -> dict:
    """Normalise a single gate's output into the convergence schema."""
    decision = _decision_from_exit_code(exit_code)
    deny_count = sum(1 for f in findings_dicts if f.get("severity") == "deny")
    warn_count = sum(1 for f in findings_dicts if f.get("severity") == "warn")

    return {
        "gate_id": gate_id,
        "gate_name": gate_name,
        "decision": decision,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "findings_total": len(findings_dicts),
        "findings_deny": deny_count,
        "findings_warn": warn_count,
        "artifacts_checked": artifacts_checked,
        "report_path_json": report_paths.get("json"),
        "report_path_md": report_paths.get("md"),
        "evidence_hash": evidence_hash,
        "findings": findings_dicts,
    }


def _gate_result_to_normalized(gr: GateResult) -> dict:
    """Convert a GateResult dataclass into the normalised dict schema."""
    return {
        "gate_id": gr.gate_id,
        "gate_name": gr.gate_name,
        "decision": gr.decision,
        "exit_code": gr.exit_code,
        "duration_ms": gr.duration_ms,
        "findings_total": gr.findings_total,
        "findings_deny": gr.findings_deny,
        "findings_warn": gr.findings_warn,
        "artifacts_checked": gr.artifacts_checked,
        "report_path_json": gr.report_path_json,
        "report_path_md": gr.report_path_md,
        "evidence_hash": gr.evidence_hash,
        "started_at_utc": gr.started_at_utc,
        "finished_at_utc": gr.finished_at_utc,
    }


def determine_final_decision(gate_results: list[dict]) -> str:
    """Determine overall convergence decision from normalised gate results.

    Rules (fail-closed):
      - Any gate FAIL -> FAIL
      - No FAIL but any WARN -> WARN
      - All PASS -> PASS
      - Missing evidence hash, unexpected exit code, empty results -> FAIL
    """
    if not gate_results:
        return "FAIL"  # fail-closed: no results

    has_fail = False
    has_warn = False

    for gr in gate_results:
        decision = gr.get("decision", "FAIL")

        # Fail-closed checks
        if decision not in ("PASS", "WARN", "FAIL"):
            return "FAIL"
        if not gr.get("evidence_hash"):
            return "FAIL"

        if decision == "FAIL":
            has_fail = True
        elif decision == "WARN":
            has_warn = True

    if has_fail:
        return "FAIL"
    if has_warn:
        return "WARN"
    return "PASS"


def aggregate_gate_results(gate_results: list[dict]) -> dict:
    """Aggregate normalised gate results into the convergence report body."""
    run_started = _utc_now_iso()

    final_decision = determine_final_decision(gate_results)

    total_findings = sum(gr.get("findings_total", 0) for gr in gate_results)
    total_deny = sum(gr.get("findings_deny", 0) for gr in gate_results)
    total_warn = sum(gr.get("findings_warn", 0) for gr in gate_results)
    total_duration_ms = sum(gr.get("duration_ms", 0) for gr in gate_results)
    total_artifacts = max((gr.get("artifacts_checked", 0) for gr in gate_results), default=0)

    gates_passed = [gr["gate_id"] for gr in gate_results if gr.get("decision") == "PASS"]
    gates_warned = [gr["gate_id"] for gr in gate_results if gr.get("decision") == "WARN"]
    gates_failed = [gr["gate_id"] for gr in gate_results if gr.get("decision") == "FAIL"]

    # Convergence evidence hash: hash of all gate evidence hashes
    evidence_inputs = [gr.get("evidence_hash", "") for gr in gate_results]
    convergence_evidence_hash = _json_sha256(evidence_inputs)

    # Convergence-level findings for orchestrator errors
    convergence_findings: list[dict] = []
    for gr in gate_results:
        if not gr.get("evidence_hash"):
            convergence_findings.append(
                {
                    "class": "gate_evidence_missing",
                    "severity": "deny",
                    "path": gr.get("gate_id", "unknown"),
                    "detail": f"gate '{gr.get('gate_name', '?')}' has no evidence hash",
                }
            )

    if gates_failed:
        convergence_findings.append(
            {
                "class": "convergence_fail_closed",
                "severity": "deny",
                "path": "convergence",
                "detail": f"gate(s) failed: {', '.join(gates_failed)}",
            }
        )

    if gates_warned and not gates_failed:
        convergence_findings.append(
            {
                "class": "convergence_warn_present",
                "severity": "warn",
                "path": "convergence",
                "detail": f"gate(s) warned: {', '.join(gates_warned)}",
            }
        )

    return {
        "report_type": "reference_gates_convergence",
        "report_version": "1.0.0",
        "timestamp_utc": run_started,
        "final_decision": final_decision,
        "totals": {
            "gates_executed": len(gate_results),
            "gates_passed": len(gates_passed),
            "gates_warned": len(gates_warned),
            "gates_failed": len(gates_failed),
            "findings_total": total_findings,
            "findings_deny": total_deny,
            "findings_warn": total_warn,
            "total_duration_ms": total_duration_ms,
            "artifacts_checked": total_artifacts,
        },
        "gates_passed": gates_passed,
        "gates_warned": gates_warned,
        "gates_failed": gates_failed,
        "gates": gate_results,
        "convergence_findings": convergence_findings,
        "evidence_hash": convergence_evidence_hash,
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "hostname": platform.node(),
            "generator": "run_all_reference_gates.py",
        },
    }


# ---------------------------------------------------------------------------
# Report emitters
# ---------------------------------------------------------------------------
def emit_convergence_report(report: dict, output_dir: Path) -> None:
    """Write JSON and Markdown convergence reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- JSON ---
    json_path = output_dir / CONVERGENCE_REPORT_JSON
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- Markdown ---
    md_path = output_dir / CONVERGENCE_REPORT_MD
    md_path.write_text(
        _render_markdown(report),
        encoding="utf-8",
    )


def _render_markdown(report: dict) -> str:
    """Render the convergence Markdown report."""
    lines: list[str] = []
    decision = report.get("final_decision", "UNKNOWN")
    totals = report.get("totals", {})
    ts = report.get("timestamp_utc", "N/A")

    # --- Executive Summary ---
    lines.append("# Reference Gates Convergence Report")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Final Decision | **{decision}** |")
    lines.append(f"| Timestamp | {ts} |")
    lines.append(f"| Gates Executed | {totals.get('gates_executed', 0)} |")
    lines.append(f"| Gates Passed | {totals.get('gates_passed', 0)} |")
    lines.append(f"| Gates Warned | {totals.get('gates_warned', 0)} |")
    lines.append(f"| Gates Failed | {totals.get('gates_failed', 0)} |")
    lines.append(f"| Total Findings | {totals.get('findings_total', 0)} |")
    lines.append(f"| Deny Findings | {totals.get('findings_deny', 0)} |")
    lines.append(f"| Warn Findings | {totals.get('findings_warn', 0)} |")
    lines.append(f"| Total Duration | {totals.get('total_duration_ms', 0)} ms |")
    lines.append(f"| Evidence Hash | `{report.get('evidence_hash', 'N/A')[:16]}...` |")
    lines.append("")

    # --- Gate Matrix ---
    lines.append("## Gate Matrix")
    lines.append("")
    lines.append("| # | Gate | Decision | Findings | Deny | Warn | Duration (ms) |")
    lines.append("|---|------|----------|----------|------|------|---------------|")
    for i, gate in enumerate(report.get("gates", []), 1):
        lines.append(
            f"| {i} "
            f"| {gate.get('gate_name', '?')} "
            f"| **{gate.get('decision', '?')}** "
            f"| {gate.get('findings_total', 0)} "
            f"| {gate.get('findings_deny', 0)} "
            f"| {gate.get('findings_warn', 0)} "
            f"| {gate.get('duration_ms', 0)} |"
        )
    lines.append("")

    # --- Findings Aggregation ---
    lines.append("## Findings Aggregation")
    lines.append("")
    all_findings_exist = False
    for gate in report.get("gates", []):
        gate_findings = gate.get("findings", [])
        if gate_findings:
            all_findings_exist = True
            lines.append(f"### {gate.get('gate_name', '?')}")
            lines.append("")
            for f in gate_findings:
                sev = f.get("severity", "?").upper()
                tag = "FAIL" if sev == "DENY" else sev
                lines.append(f"- **[{tag}]** `{f.get('class', '?')}`: {f.get('path', '?')}")
                lines.append(f"  - {f.get('detail', '')}")
            lines.append("")
    if not all_findings_exist:
        lines.append("No findings across all gates.")
        lines.append("")

    # --- Convergence Findings ---
    conv_findings = report.get("convergence_findings", [])
    if conv_findings:
        lines.append("## Convergence Findings")
        lines.append("")
        for f in conv_findings:
            sev = f.get("severity", "?").upper()
            tag = "FAIL" if sev == "DENY" else sev
            lines.append(f"- **[{tag}]** `{f.get('class', '?')}`: {f.get('detail', '')}")
        lines.append("")

    # --- Failed / Warned Gates ---
    gates_failed = report.get("gates_failed", [])
    gates_warned = report.get("gates_warned", [])
    if gates_failed or gates_warned:
        lines.append("## Failed / Warned Gates")
        lines.append("")
        if gates_failed:
            lines.append(f"- **Failed**: {', '.join(gates_failed)}")
        if gates_warned:
            lines.append(f"- **Warned**: {', '.join(gates_warned)}")
        lines.append("")

    # --- Final Decision ---
    lines.append("## Final Decision")
    lines.append("")
    lines.append(f"**{decision}**")
    lines.append("")

    # --- Evidence / Artifact Paths ---
    lines.append("## Evidence / Artifact Paths")
    lines.append("")
    lines.append(f"- Convergence Evidence Hash: `{report.get('evidence_hash', 'N/A')}`")
    for gate in report.get("gates", []):
        gid = gate.get("gate_id", "?")
        lines.append(f"- `{gid}` evidence: `{gate.get('evidence_hash', 'N/A')[:16]}...`")
        if gate.get("report_path_json"):
            lines.append(f"  - JSON: `{gate['report_path_json']}`")
        if gate.get("report_path_md"):
            lines.append(f"  - Markdown: `{gate['report_path_md']}`")
    lines.append("")

    # --- Environment ---
    env_info = report.get("environment", {})
    if env_info:
        lines.append("## Environment")
        lines.append("")
        for k, v in env_info.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_all_reference_gates.py",
        description="Convergence orchestrator — runs all 4 SoT/reference gates and produces a unified report.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="SSID repo root (default: auto-detect from script location)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="report output directory (default: <repo>/02_audit_logging/reports/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON report to stdout",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="print Markdown report to stdout",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="only check that convergence reports exist (do not re-run gates)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="stop after first gate FAIL",
    )
    parser.add_argument(
        "--include",
        default=None,
        help=f"comma-separated gate IDs to run (default: all). Available: {', '.join(GATE_ORDER)}",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="per-gate timeout in seconds (applies to subprocess-based gates)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo = Path(args.repo_root).resolve() if args.repo_root else _detect_repo_root()
    output_dir = Path(args.output_dir) if args.output_dir else repo / "02_audit_logging" / "reports"

    # --- --verify-only mode ---
    if args.verify_only:
        json_path = output_dir / CONVERGENCE_REPORT_JSON
        md_path = output_dir / CONVERGENCE_REPORT_MD
        json_ok = json_path.exists()
        md_ok = md_path.exists()

        if json_ok:
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "final_decision" not in data:
                    json_ok = False
            except Exception:
                json_ok = False

        if args.json:
            print(
                json.dumps(
                    {
                        "verify_only": True,
                        "json_report_exists": json_ok,
                        "md_report_exists": md_ok,
                        "json_path": str(json_path),
                        "md_path": str(md_path),
                        "valid": json_ok and md_ok,
                    },
                    indent=2,
                )
            )
        else:
            status = "PASS" if (json_ok and md_ok) else "FAIL"
            print(f"Convergence Report Verification: {status}")
            print(f"  JSON: {'OK' if json_ok else 'MISSING/INVALID'} ({json_path})")
            print(f"  MD:   {'OK' if md_ok else 'MISSING/INVALID'} ({md_path})")

        return EXIT_PASS if (json_ok and md_ok) else EXIT_FAIL

    # --- Determine which gates to run ---
    if args.include:
        requested = [g.strip() for g in args.include.split(",") if g.strip()]
        # Validate
        for gid in requested:
            if gid not in GATE_ORDER:
                print(f"ERROR: unknown gate ID '{gid}'. Available: {', '.join(GATE_ORDER)}")
                return EXIT_FAIL
        gates_to_run = [g for g in GATE_ORDER if g in requested]
    else:
        gates_to_run = list(GATE_ORDER)

    # --- Gate runner dispatch ---
    gate_runners: dict[str, Any] = {
        GATE_SOT_VALIDATOR: lambda: run_sot_validator(repo, args.timeout_seconds),
        GATE_XREF_AUDIT: lambda: run_reference_audit(repo),
        GATE_SYNC_GUARD: lambda: run_sync_guard(repo),
        GATE_BASELINE_GATE: lambda: run_baseline_gate(repo),
    }

    gate_results: list[dict] = []
    aborted = False

    for gate_id in gates_to_run:
        runner = gate_runners[gate_id]
        try:
            gr = runner()
            normalized = _gate_result_to_normalized(gr)
        except Exception as exc:
            # Fail-closed: gate crashed entirely
            normalized = {
                "gate_id": gate_id,
                "gate_name": GATE_NAMES.get(gate_id, gate_id),
                "decision": "FAIL",
                "exit_code": 2,
                "duration_ms": 0,
                "findings_total": 1,
                "findings_deny": 1,
                "findings_warn": 0,
                "artifacts_checked": 0,
                "report_path_json": None,
                "report_path_md": None,
                "evidence_hash": _json_sha256(
                    [
                        {
                            "class": "gate_execution_failed",
                            "severity": "deny",
                            "path": gate_id,
                            "detail": str(exc),
                        }
                    ]
                ),
                "started_at_utc": _utc_now_iso(),
                "finished_at_utc": _utc_now_iso(),
                "findings": [
                    {
                        "class": "gate_execution_failed",
                        "severity": "deny",
                        "path": gate_id,
                        "detail": f"gate crashed: {exc}",
                    }
                ],
            }

        gate_results.append(normalized)

        if args.fail_fast and normalized.get("decision") == "FAIL":
            aborted = True
            # Add findings for skipped gates
            for skipped_id in gates_to_run:
                if skipped_id not in [gr.get("gate_id") for gr in gate_results]:
                    gate_results.append(
                        {
                            "gate_id": skipped_id,
                            "gate_name": GATE_NAMES.get(skipped_id, skipped_id),
                            "decision": "FAIL",
                            "exit_code": 2,
                            "duration_ms": 0,
                            "findings_total": 1,
                            "findings_deny": 1,
                            "findings_warn": 0,
                            "artifacts_checked": 0,
                            "report_path_json": None,
                            "report_path_md": None,
                            "evidence_hash": _json_sha256(
                                [
                                    {
                                        "class": "convergence_fail_closed",
                                        "severity": "deny",
                                        "path": skipped_id,
                                        "detail": "skipped due to --fail-fast after previous gate failure",
                                    }
                                ]
                            ),
                            "started_at_utc": _utc_now_iso(),
                            "finished_at_utc": _utc_now_iso(),
                            "findings": [
                                {
                                    "class": "convergence_fail_closed",
                                    "severity": "deny",
                                    "path": skipped_id,
                                    "detail": "skipped due to --fail-fast after previous gate failure",
                                }
                            ],
                        }
                    )
            break

    # --- Aggregate ---
    report = aggregate_gate_results(gate_results)
    if aborted:
        report["aborted_fail_fast"] = True

    # --- Emit reports ---
    emit_convergence_report(report, output_dir)

    json_path = output_dir / CONVERGENCE_REPORT_JSON
    md_path = output_dir / CONVERGENCE_REPORT_MD

    # --- Console output ---
    final_decision = report["final_decision"]
    totals = report["totals"]

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        print(_render_markdown(report))
    else:
        print(f"Reference Gates Convergence: {final_decision}")
        print(
            f"  Gates: {totals['gates_executed']} executed, "
            f"{totals['gates_passed']} passed, "
            f"{totals['gates_warned']} warned, "
            f"{totals['gates_failed']} failed"
        )
        print(
            f"  Findings: {totals['findings_total']} (deny={totals['findings_deny']}, warn={totals['findings_warn']})"
        )
        print(f"  Duration: {totals['total_duration_ms']} ms")
        print(f"  Evidence: {report['evidence_hash'][:16]}...")
        print()

        for gate in report.get("gates", []):
            marker = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}.get(gate.get("decision", "?"), "??")
            print(
                f"  [{marker}] {gate.get('gate_name', '?')}: {gate.get('decision', '?')} "
                f"({gate.get('findings_total', 0)} findings, "
                f"{gate.get('duration_ms', 0)} ms)"
            )

        if aborted:
            print()
            print("  (aborted: --fail-fast triggered)")

        print(f"\n  Reports: {json_path}")
        print(f"           {md_path}")

    if final_decision == "FAIL":
        return EXIT_FAIL
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
