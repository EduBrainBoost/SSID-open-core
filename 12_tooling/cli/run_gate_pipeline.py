#!/usr/bin/env python3
"""
Unified Gate Pipeline Runner.

Orchestrates the canonical gate chain with a single pipeline run identity:
1. Registry Canonicalization
2. Registry Enforcement
3. Promotion Gate
4. Remediation Planner

Outputs:
- gate_pipeline_summary.json
- gate_pipeline_report.md
- gate_pipeline_run_ledger.json

Exit codes:
- 0 PASS
- 1 WARN
- 2 DENY
- 3 ERROR
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_DENY = 2
EXIT_ERROR = 3

REPORT_REL = "02_audit_logging/reports"
REGISTRY_REF = "24_meta_orchestration/registry/sot_registry.json"
DEFAULT_EMS_URL = "http://localhost:8000/api/gates"
_CLI_DIR = Path(__file__).resolve().parent
_CHILD_ENV_KEYS = (
    "GATE_CORRELATION_ID",
    "GATE_PARENT_RUN_ID",
    "GATE_COMMIT_SHA",
    "PR_NUMBER",
    "GATE_TRIGGER",
)

_STAGE_ORDER = [
    ("canonicalization", "run_registry_canonicalization.py", "run_canonicalization"),
    ("registry_enforcement", "run_registry_enforcement.py", "run_enforcement"),
    ("promotion_gate", "run_promotion_gate.py", "run_promotion_gate"),
    ("remediation_planner", "run_gate_remediation_planner.py", "run_remediation_planner"),
]
_DECISION_RANK = {"PASS": 0, "WARN": 1, "DENY": 2, "ERROR": 3}
_REMEDIATION_WARN = {"MANUAL_REVIEW", "WARN"}
_REMEDIATION_PASS = {"AUTO_FIXABLE", "CLEAN", "PASS"}

_loaded_modules: dict[str, Any] = {}


def _load_module(module_name: str, filename: str) -> Any:
    if filename in _loaded_modules:
        return _loaded_modules[filename]
    module_path = _CLI_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec for {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    _loaded_modules[filename] = mod
    return mod


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(repo_root: Path, *args: str) -> str:
    try:
        cp = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if cp.returncode != 0:
        return ""
    return cp.stdout.strip()


def _detect_commit_sha(repo_root: Path) -> str:
    return (
        os.environ.get("GATE_COMMIT_SHA")
        or os.environ.get("GITHUB_SHA")
        or _git(repo_root, "rev-parse", "HEAD")
    )


def _detect_pr_number() -> int | None:
    candidates = [
        os.environ.get("PR_NUMBER", ""),
        os.environ.get("GITHUB_PR_NUMBER", ""),
    ]
    for raw in candidates:
        if raw.isdigit():
            return int(raw)
    ref = os.environ.get("GITHUB_REF", "")
    match = re.match(r"refs/pull/(\d+)/", ref)
    if match:
        return int(match.group(1))
    return None


def _detect_trigger() -> str:
    explicit = os.environ.get("GATE_TRIGGER")
    if explicit:
        return explicit
    if any(os.environ.get(v) for v in ("CI", "GITHUB_ACTIONS", "GITLAB_CI")):
        return "ci"
    return "manual"


def _decision_to_exit(status: str) -> int:
    return {
        "PASS": EXIT_PASS,
        "WARN": EXIT_WARN,
        "DENY": EXIT_DENY,
        "ERROR": EXIT_ERROR,
    }.get(status.upper(), EXIT_ERROR)


def _normalize_status(status: Any) -> str:
    raw = str(status or "PASS").strip().upper()
    aliases = {
        "FAIL": "DENY",
        "BLOCKED": "DENY",
        "HARD_BLOCK": "DENY",
        "WARNING": "WARN",
    }
    return aliases.get(raw, raw or "PASS")


def _normalize_severity(value: Any) -> str:
    raw = str(value or "info").strip().lower()
    if raw in {"deny", "hard_block", "blocker", "critical", "error", "fail"}:
        return "deny"
    if raw in {"warn", "warning", "manual_review", "manual_review_required", "required", "high"}:
        return "warn"
    return "info"


def _ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _collect_refs(findings: list[dict[str, Any]]) -> dict[str, list[str]]:
    evidence_refs: set[str] = set()
    source_refs: set[str] = set()
    registry_refs: set[str] = {REGISTRY_REF}
    for finding in findings:
        for key, target in (
            ("evidence_ref", evidence_refs),
            ("source_of_truth_ref", source_refs),
        ):
            ref = finding.get(key)
            if isinstance(ref, str) and ref:
                target.add(ref)
            elif isinstance(ref, dict):
                path = ref.get("path")
                ref_hash = ref.get("hash")
                if isinstance(path, str) and path:
                    target.add(path)
                if isinstance(ref_hash, str) and ref_hash:
                    target.add(f"sha256:{ref_hash}")
    return {
        "registry_refs": sorted(registry_refs),
        "evidence_refs": sorted(evidence_refs),
        "source_of_truth_refs": sorted(source_refs),
    }


def _normalize_findings(
    stage: str,
    stage_run_id: str,
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        item.setdefault("id", f"{stage_run_id}:{len(normalized) + 1}")
        item["stage"] = stage
        item["stage_run_id"] = stage_run_id
        item["severity"] = _normalize_severity(item.get("severity"))
        normalized.append(item)
    return normalized


def _build_stage_ledger(
    *,
    stage_name: str,
    stage_run_id: str,
    stage_result: dict[str, Any],
    repo_root: Path,
    related_repo: str,
    correlation_id: str,
    parent_run_id: str,
    commit_sha: str,
    pr_number: int | None,
    trigger: str,
) -> dict[str, Any]:
    findings = _normalize_findings(stage_name, stage_run_id, _ensure_list(stage_result.get("findings")))
    refs = _collect_refs(findings)
    artifacts = sorted({f.get("path", "") for f in findings if f.get("path")})
    decision = _normalize_status(stage_result.get("status"))
    started_at = stage_result.get("timestamp_utc") or _utc_now()
    finished_at = _utc_now()
    summary = dict(stage_result.get("summary", {})) if isinstance(stage_result.get("summary"), dict) else {}
    summary.setdefault("total_findings", len(findings))
    summary.setdefault("deny", sum(1 for f in findings if f["severity"] == "deny"))
    summary.setdefault("warn", sum(1 for f in findings if f["severity"] == "warn"))
    summary.setdefault("info", sum(1 for f in findings if f["severity"] == "info"))
    return {
        "run_id": stage_run_id,
        "gate_type": stage_name,
        "repo": str(repo_root),
        "related_repo": related_repo,
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": finished_at,
        "timestamp": started_at,
        "decision": decision,
        "severity_summary": summary,
        "findings_count": len(findings),
        "findings": findings,
        "artifacts": artifacts,
        "registry_refs": refs["registry_refs"],
        "evidence_refs": refs["evidence_refs"],
        "source_of_truth_refs": refs["source_of_truth_refs"],
        "exit_code": _decision_to_exit(decision),
        "correlation_id": correlation_id,
        "parent_run_id": parent_run_id,
        "commit_sha": commit_sha,
        "pr_number": pr_number,
    }


def _aggregate_pipeline_decision(stage_ledgers: list[dict[str, Any]]) -> tuple[str, str | None]:
    blocking_stage: str | None = None
    blocking_rank = -1
    gate_ledgers = [ledger for ledger in stage_ledgers if ledger["gate_type"] != "remediation_planner"]
    remediation = next((ledger for ledger in stage_ledgers if ledger["gate_type"] == "remediation_planner"), None)

    for ledger in gate_ledgers:
        decision = _normalize_status(ledger.get("decision"))
        if decision == "ERROR":
            return "ERROR", ledger["gate_type"]
        if decision == "DENY" and _DECISION_RANK[decision] > blocking_rank:
            blocking_stage = ledger["gate_type"]
            blocking_rank = _DECISION_RANK[decision]

    if blocking_stage:
        return "DENY", blocking_stage

    if remediation is not None:
        remediation_decision = _normalize_status(remediation.get("decision"))
        if remediation_decision == "ERROR":
            return "ERROR", remediation["gate_type"]

    gate_decisions = {_normalize_status(ledger.get("decision")) for ledger in gate_ledgers}
    if "WARN" in gate_decisions:
        return "WARN", next(
            ledger["gate_type"] for ledger in gate_ledgers if _normalize_status(ledger.get("decision")) == "WARN"
        )

    if remediation is not None:
        rem = _normalize_status(remediation.get("decision"))
        if rem in _REMEDIATION_WARN:
            return "WARN", remediation["gate_type"]
        if rem not in _REMEDIATION_PASS:
            return "ERROR", remediation["gate_type"]

    return "PASS", None


def _summarize(stage_ledgers: list[dict[str, Any]], aggregated_findings: list[dict[str, Any]]) -> dict[str, Any]:
    deny = sum(1 for finding in aggregated_findings if finding["severity"] == "deny")
    warn = sum(1 for finding in aggregated_findings if finding["severity"] == "warn")
    info = sum(1 for finding in aggregated_findings if finding["severity"] == "info")
    remediation = next((ledger for ledger in stage_ledgers if ledger["gate_type"] == "remediation_planner"), None)
    remediation_summary = remediation.get("severity_summary", {}) if remediation else {}
    return {
        "total_findings": len(aggregated_findings),
        "deny": deny,
        "warn": warn,
        "info": info,
        "stages_run": len(stage_ledgers),
        "stages_passed": sum(1 for ledger in stage_ledgers if _normalize_status(ledger["decision"]) == "PASS"),
        "auto_fix_safe": remediation_summary.get("auto_fix_safe", 0),
        "manual_review_required": remediation_summary.get("manual_review_required", 0),
        "hard_block_no_fix": remediation_summary.get("hard_block_no_fix", 0),
    }


def _aggregate_artifacts(stage_ledgers: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            artifact
            for ledger in stage_ledgers
            for artifact in _ensure_list(ledger.get("artifacts"))
            if artifact
        }
    )


def _aggregate_refs(stage_ledgers: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "registry_refs": sorted(
            {
                ref
                for ledger in stage_ledgers
                for ref in _ensure_list(ledger.get("registry_refs"))
                if ref
            }
        ),
        "evidence_refs": sorted(
            {
                ref
                for ledger in stage_ledgers
                for ref in _ensure_list(ledger.get("evidence_refs"))
                if ref
            }
        ),
        "source_of_truth_refs": sorted(
            {
                ref
                for ledger in stage_ledgers
                for ref in _ensure_list(ledger.get("source_of_truth_refs"))
                if ref
            }
        ),
        "sub_run_ids": [ledger["run_id"] for ledger in stage_ledgers],
    }


def _build_stage_result(ledger: dict[str, Any], *, blocking_stage: str | None) -> dict[str, Any]:
    return {
        "stage": ledger["gate_type"],
        "status": _normalize_status(ledger["decision"]),
        "run_id": ledger["run_id"],
        "findings_count": ledger["findings_count"],
        "artifacts": ledger.get("artifacts", []),
        "refs": {
            "registry_refs": ledger.get("registry_refs", []),
            "evidence_refs": ledger.get("evidence_refs", []),
            "source_of_truth_refs": ledger.get("source_of_truth_refs", []),
        },
        "blocking": ledger["gate_type"] == blocking_stage,
    }


def _pipeline_report_md(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Gate Pipeline Report",
        "",
        f"- Pipeline Run: `{result['pipeline_run_id']}`",
        f"- Status: **{result['status']}**",
        f"- Trigger: `{result['trigger']}`",
        f"- Correlation: `{result['correlation_id']}`",
        f"- Commit: `{result.get('commit_sha') or 'unknown'}`",
        f"- PR: `{result.get('pr_number') if result.get('pr_number') is not None else 'n/a'}`",
        f"- Blocking Stage: `{result.get('blocking_stage') or 'none'}`",
        "",
        "## Executive Summary",
        "",
        f"- Checked: {', '.join(stage['stage'] for stage in result['stage_results'])}",
        f"- Findings: {summary['total_findings']} total ({summary['deny']} deny, {summary['warn']} warn, {summary['info']} info)",
        f"- Auto-fixable: {summary['auto_fix_safe']}",
        f"- Manual review: {summary['manual_review_required']}",
        f"- Hard blocks: {summary['hard_block_no_fix']}",
        f"- Promotion allowed: {'yes' if result['status'] == 'PASS' else 'no'}",
        "",
        "## Stage Results",
        "",
        "| Stage | Status | Findings | Blocking | Run ID |",
        "|-------|--------|----------|----------|--------|",
    ]
    for stage in result["stage_results"]:
        lines.append(
            f"| {stage['stage']} | **{stage['status']}** | {stage['findings_count']} | "
            f"{'yes' if stage['blocking'] else 'no'} | `{stage['run_id']}` |"
        )
    lines.extend(["", "## Aggregated Findings", ""])
    if result["aggregated_findings"]:
        lines.extend(
            [
                "| ID | Stage | Severity | Path | Details |",
                "|----|-------|----------|------|---------|",
            ]
        )
        for finding in result["aggregated_findings"]:
            details = str(finding.get("details", "")).replace("|", "\\|")
            lines.append(
                f"| `{finding.get('id', '-')}` | {finding.get('stage', '-')} | {finding.get('severity', '-')}"
                f" | `{finding.get('path', '-')}` | {details} |"
            )
    else:
        lines.append("No findings.")
    lines.extend(
        [
            "",
            "## Sub-Runs",
            "",
            "| Run ID | Gate | Decision | Correlation | Parent |",
            "|--------|------|----------|-------------|--------|",
        ]
    )
    for ledger in result["sub_runs"]:
        lines.append(
            f"| `{ledger['run_id']}` | {ledger['gate_type']} | {ledger['decision']} | "
            f"`{ledger['correlation_id']}` | `{ledger['parent_run_id']}` |"
        )
    lines.extend(["", f"Generated at {result['timestamp_utc']}"])
    return "\n".join(lines) + "\n"


def _pipeline_summary_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False)


def _pipeline_ledger(result: dict[str, Any], canonical_root: Path, derivative_root: Path | None) -> dict[str, Any]:
    return {
        "run_id": result["pipeline_run_id"],
        "gate_type": "gate_pipeline",
        "repo": str(canonical_root),
        "related_repo": str(derivative_root) if derivative_root else "",
        "trigger": result["trigger"],
        "started_at": result["timestamp_utc"],
        "finished_at": result["finished_at"],
        "timestamp": result["timestamp_utc"],
        "decision": result["status"],
        "severity_summary": result["summary"],
        "findings_count": len(result["aggregated_findings"]),
        "findings": result["aggregated_findings"],
        "artifacts": result["aggregated_artifacts"],
        "registry_refs": result["aggregated_refs"]["registry_refs"],
        "evidence_refs": result["aggregated_refs"]["evidence_refs"],
        "source_of_truth_refs": result["aggregated_refs"]["source_of_truth_refs"],
        "exit_code": _decision_to_exit(result["status"]),
        "correlation_id": result["correlation_id"],
        "parent_run_id": "",
        "commit_sha": result["commit_sha"],
        "pr_number": result["pr_number"],
        "blocking_stage": result["blocking_stage"],
        "stage_results": result["stage_results"],
        "sub_runs": result["sub_runs"],
        "promotion_allowed": result["status"] == "PASS",
    }


def _ingest_record(base_url: str, record: dict[str, Any]) -> None:
    endpoint = f"{base_url.rstrip('/')}/runs/ingest"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(record).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 300:
            raise RuntimeError(f"EMS ingest failed with HTTP {response.status}")


def _ingest_ems(base_url: str, pipeline_ledger: dict[str, Any], sub_runs: list[dict[str, Any]]) -> None:
    records = [pipeline_ledger, *sub_runs]
    errors: list[str] = []
    for record in records:
        try:
            _ingest_record(base_url, record)
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            errors.append(f"{record['run_id']}: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))


@contextmanager
def _pipeline_env(correlation_id: str, pipeline_run_id: str, commit_sha: str, pr_number: int | None, trigger: str) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in _CHILD_ENV_KEYS}
    os.environ["GATE_CORRELATION_ID"] = correlation_id
    os.environ["GATE_PARENT_RUN_ID"] = pipeline_run_id
    os.environ["GATE_COMMIT_SHA"] = commit_sha
    os.environ["GATE_TRIGGER"] = trigger
    if pr_number is None:
        os.environ.pop("PR_NUMBER", None)
    else:
        os.environ["PR_NUMBER"] = str(pr_number)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _stage_run_id(stage_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stage_name}_{stamp}_{uuid4().hex[:8]}"


def run_gate_pipeline(
    canonical_root: Path,
    derivative_root: Path | None = None,
    output_dir: Path | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    timestamp_utc = _utc_now()
    pipeline_run_id = f"gate_pipeline_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    correlation_id = pipeline_run_id
    commit_sha = _detect_commit_sha(canonical_root)
    pr_number = _detect_pr_number()
    trigger = _detect_trigger()
    resolved_output = output_dir or canonical_root / REPORT_REL
    related_repo = str(derivative_root) if derivative_root else ""

    stage_ledgers: list[dict[str, Any]] = []

    with _pipeline_env(correlation_id, pipeline_run_id, commit_sha, pr_number, trigger):
        for stage_name, filename, attr_name in _STAGE_ORDER:
            stage_run_id = _stage_run_id(stage_name)
            try:
                module = _load_module(attr_name, filename)
                if stage_name == "canonicalization":
                    stage_result = getattr(module, attr_name)(canonical_root, resolved_output, strict=strict)
                elif stage_name == "registry_enforcement":
                    stage_result = getattr(module, attr_name)(canonical_root, resolved_output, strict=strict)
                elif stage_name == "promotion_gate":
                    if derivative_root is None:
                        stage_result = {
                            "timestamp_utc": _utc_now(),
                            "status": "PASS",
                            "summary": {"total_findings": 0, "deny": 0, "warn": 0, "skipped": True},
                            "findings": [],
                        }
                    else:
                        stage_result = getattr(module, attr_name)(canonical_root, derivative_root, resolved_output, strict=strict)
                else:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        suffix=".json",
                        prefix="gate_pipeline_findings_",
                        delete=False,
                        encoding="utf-8",
                    ) as handle:
                        findings_payload = []
                        for ledger in stage_ledgers:
                            findings_payload.extend(ledger.get("findings", []))
                        json.dump({"findings": findings_payload}, handle, indent=2)
                        findings_path = handle.name
                    try:
                        stage_result = getattr(module, attr_name)(
                            findings_path=findings_path,
                            repo_root=str(canonical_root),
                            output_dir=str(resolved_output),
                        )
                    finally:
                        try:
                            os.unlink(findings_path)
                        except OSError:
                            pass
            except Exception as exc:
                stage_result = {
                    "timestamp_utc": _utc_now(),
                    "status": "ERROR",
                    "summary": {"total_findings": 0, "deny": 0, "warn": 0, "info": 0, "error": str(exc)},
                    "findings": [],
                }

            stage_ledgers.append(
                _build_stage_ledger(
                    stage_name=stage_name,
                    stage_run_id=stage_run_id,
                    stage_result=stage_result,
                    repo_root=canonical_root,
                    related_repo=related_repo,
                    correlation_id=correlation_id,
                    parent_run_id=pipeline_run_id,
                    commit_sha=commit_sha,
                    pr_number=pr_number,
                    trigger=trigger,
                )
            )

    aggregated_findings = [
        finding
        for ledger in stage_ledgers
        if ledger["gate_type"] != "remediation_planner"
        for finding in ledger.get("findings", [])
    ]
    pipeline_status, blocking_stage = _aggregate_pipeline_decision(stage_ledgers)
    stage_results = [_build_stage_result(ledger, blocking_stage=blocking_stage) for ledger in stage_ledgers]
    aggregated_refs = _aggregate_refs(stage_ledgers)
    result = {
        "gate": "gate_pipeline",
        "pipeline_run_id": pipeline_run_id,
        "status": pipeline_status,
        "blocking_stage": blocking_stage,
        "stage_results": stage_results,
        "aggregated_findings": aggregated_findings,
        "aggregated_artifacts": _aggregate_artifacts(stage_ledgers),
        "aggregated_refs": aggregated_refs,
        "summary": _summarize(stage_ledgers, aggregated_findings),
        "correlation_id": correlation_id,
        "commit_sha": commit_sha,
        "pr_number": pr_number,
        "trigger": trigger,
        "timestamp_utc": timestamp_utc,
        "finished_at": _utc_now(),
        "sub_runs": stage_ledgers,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_gate_pipeline",
        description="Run the unified canonical gate pipeline.",
    )
    parser.add_argument("--canonical-repo", required=True, help="Path to SSID canonical repo")
    parser.add_argument("--derivative-repo", default=None, help="Path to derivative repo")
    parser.add_argument("--output-dir", default=None, help=f"Output directory (default: <canonical-repo>/{REPORT_REL})")
    parser.add_argument("--strict", action="store_true", help="Enable strict gate behaviour")
    parser.add_argument("--emit-run-ledger", action="store_true", help="Write gate_pipeline_run_ledger.json")
    parser.add_argument(
        "--ingest-ems",
        nargs="?",
        const=DEFAULT_EMS_URL,
        default=None,
        help="Optionally ingest pipeline + sub-run ledgers into EMS (default URL when omitted).",
    )
    parser.add_argument("--verify-only", action="store_true", help="Run without writing output files")
    args = parser.parse_args()

    canonical_root = Path(args.canonical_repo).resolve()
    derivative_root = Path(args.derivative_repo).resolve() if args.derivative_repo else None
    output_dir = Path(args.output_dir).resolve() if args.output_dir else canonical_root / REPORT_REL

    if not canonical_root.is_dir():
        print(f"ERROR: canonical repo not found: {canonical_root}", file=sys.stderr)
        return EXIT_ERROR
    if derivative_root is not None and not derivative_root.is_dir():
        print(f"ERROR: derivative repo not found: {derivative_root}", file=sys.stderr)
        return EXIT_ERROR

    try:
        result = run_gate_pipeline(
            canonical_root=canonical_root,
            derivative_root=derivative_root,
            output_dir=output_dir,
            strict=args.strict,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(
        f"GATE_PIPELINE: {result['status']} "
        f"(findings={result['summary']['total_findings']}, deny={result['summary']['deny']}, "
        f"warn={result['summary']['warn']}, blocking_stage={result.get('blocking_stage') or 'none'})"
    )
    for stage in result["stage_results"]:
        print(
            f"  STAGE {stage['stage']}: {stage['status']} "
            f"(findings={stage['findings_count']}, run_id={stage['run_id']})"
        )

    pipeline_ledger = _pipeline_ledger(result, canonical_root, derivative_root)

    if not args.verify_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "gate_pipeline_summary.json").write_text(
            _pipeline_summary_json(result),
            encoding="utf-8",
        )
        (output_dir / "gate_pipeline_report.md").write_text(
            _pipeline_report_md(result),
            encoding="utf-8",
        )
        if args.emit_run_ledger:
            (output_dir / "gate_pipeline_run_ledger.json").write_text(
                json.dumps(pipeline_ledger, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            for sub_run in result["sub_runs"]:
                (output_dir / f"{sub_run['run_id']}_run_ledger.json").write_text(
                    json.dumps(sub_run, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

    if args.ingest_ems:
        try:
            _ingest_ems(args.ingest_ems, pipeline_ledger, result["sub_runs"])
            print(f"EMS_INGEST: {args.ingest_ems}")
        except Exception as exc:
            print(f"EMS_INGEST_ERROR: {exc}", file=sys.stderr)
            return EXIT_ERROR

    return _decision_to_exit(result["status"])


if __name__ == "__main__":
    raise SystemExit(main())
