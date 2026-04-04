# DEPRECATED: REDUNDANT — Canonical tool is 12_tooling/cli/sot_sync_guard.py
# Dependencies: 12_tooling/tests/test_full_convergence_e2e.py, test_golden_regression.py,
#   test_sot_validation_ingest_e2e.py
#!/usr/bin/env python3
"""Unified SoT Convergence Validation Runner.

Pipeline: scan -> manifest -> opencore_sync -> policy_check -> report -> exit

Exit codes: 0=success, 1=warn, 2=deny, 3=system_error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
from validation.convergence_manifest_gen import SchemaError, generate_manifest, render_report
from validation.sot_convergence_scanner import scan as scanner_scan
from validation.validate_opencore_sync import scan as opencore_scan

EXIT_SUCCESS, EXIT_WARN, EXIT_DENY, EXIT_SYSTEM_ERROR = 0, 1, 2, 3
_CONTRACT_REL = "16_codex/contracts/sot/sot_contract.yaml"
_SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_REPORT_SCHEMA = "sot_validation_report.schema.json"
_REPORT_REQUIRED = (
    "report_version",
    "run_identity",
    "generated_at_utc",
    "exit_code",
    "exit_label",
    "decision",
    "summary",
    "findings",
)


def _validate_against_schema(data: dict[str, Any], schema_name: str) -> list[str]:
    """Validate *data* against a JSON Schema file in _SCHEMA_DIR.

    Returns a list of human-readable error strings (empty on success).
    """
    schema_path = _SCHEMA_DIR / schema_name
    if not schema_path.is_file():
        return [f"schema file not found: {schema_path}"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"failed to load schema {schema_name}: {exc}"]
    resolver = jsonschema.RefResolver(
        base_uri=schema_path.as_uri(),
        referrer=schema,
    )
    errors: list[str] = []
    validator = jsonschema.Draft7Validator(schema, resolver=resolver)
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return errors


def _normalize(raw: dict[str, Any], source: str, idx: int) -> dict[str, Any]:
    detail_text = raw.get("detail", raw.get("details", ""))
    entry = {
        "id": f"{source}-{idx:04d}",
        "class": raw.get("class", "unknown"),
        "severity": raw.get("severity", "info"),
        "source": source,
        "path": raw.get("path", ""),
        "details": detail_text,
        "timestamp": raw.get("timestamp", ""),
        "repo": raw.get("repo", ""),
        "evidence_hash": raw.get("evidence_hash", ""),
    }
    return entry


def _sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def _git_head(repo: Path) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _contract_version(p: Path) -> str:
    if not p.is_file():
        return "unknown"
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip().startswith("version:"):
            return ln.split(":", 1)[1].strip().strip("'\"")
    return "unknown"


# ---------------------------------------------------------------------------
# Policy engine — Python-based Rego-equivalent (full implementation)
# ---------------------------------------------------------------------------


def _finding(
    rule_id: str, cls: str, severity: str, path: str, detail: str, repo: str = "", ts: str = "", evidence_hash: str = ""
) -> dict[str, Any]:
    """Construct a policy finding with full traceability fields."""
    if not ts:
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = {
        "class": cls,
        "severity": severity,
        "path": path,
        "detail": detail,
        "repo": repo,
        "timestamp": ts,
        "evidence_hash": evidence_hash,
        "rule_id": rule_id,
    }
    if not evidence_hash:
        raw["evidence_hash"] = _sha256_str(json.dumps(raw, sort_keys=True))
    return raw


def _eval_convergence(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate sot_convergence_policy.rego rules (D-001..D-004, W-001..W-004, I-001..I-002)."""
    out: list[dict[str, Any]] = []
    _a = out.append
    drift = scan.get("drift_findings", [])
    repo_name = scan.get("repo_name", "unknown")
    repo_role = scan.get("repo_role", "unknown")
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # D-001: Overall status FAIL is unconditional deny
    if scan.get("status") == "FAIL":
        _a(
            _finding(
                "D-001",
                "policy_deny",
                "critical",
                "",
                f"CONVERGENCE_DENY: repo {repo_name} reported status FAIL",
                repo=repo_name,
                ts=ts,
            )
        )

    # D-002: Canonical repos must not have missing artifacts
    missing = scan.get("missing_artifacts", [])
    if repo_role == "canonical" and missing:
        _a(
            _finding(
                "D-002",
                "policy_deny",
                "critical",
                "",
                f"CONVERGENCE_DENY: canonical repo {repo_name} has {len(missing)} missing artifacts: {missing}",
                repo=repo_name,
                ts=ts,
            )
        )

    for f in drift:
        c = f.get("class", "")
        s = f.get("severity", "info")
        p = f.get("path", "")
        d = f.get("detail", "")

        # D-003: Protected scope attempts are always denied
        if c == "protected_scope_attempt":
            _a(
                _finding(
                    "D-003",
                    "policy_deny",
                    "critical",
                    p,
                    f"CONVERGENCE_DENY: protected scope attempt in {p} — {d} (severity: {s})",
                    repo=repo_name,
                    ts=ts,
                )
            )

        # D-004: Critical-severity drift findings are denied
        if s == "critical":
            _a(
                _finding(
                    "D-004",
                    "policy_deny",
                    "critical",
                    p,
                    f"CONVERGENCE_DENY: critical drift in {p} — {d} (class: {c})",
                    repo=repo_name,
                    ts=ts,
                )
            )

        # W-003: High-severity drift findings
        if s == "high":
            _a(
                _finding(
                    "W-003",
                    "policy_warn",
                    "high",
                    p,
                    f"CONVERGENCE_WARN: high-severity drift in {p} — {d} (class: {c})",
                    repo=repo_name,
                    ts=ts,
                )
            )

        # W-004: Stale derivative binding
        if c == "stale_derivative_binding":
            _a(
                _finding(
                    "W-004",
                    "policy_warn",
                    "medium",
                    p,
                    f"CONVERGENCE_WARN: stale derivative binding at {p} — {d}",
                    repo=repo_name,
                    ts=ts,
                )
            )

        # I-001: Enforcement gap findings surfaced as info
        if c == "enforcement_gap":
            _a(
                _finding(
                    "I-001",
                    "policy_info",
                    "info",
                    p,
                    f"CONVERGENCE_INFO: enforcement gap at {p} — {d} (severity: {s})",
                    repo=repo_name,
                    ts=ts,
                )
            )

        # I-002: Medium drift findings as info
        if s == "medium":
            _a(
                _finding(
                    "I-002",
                    "policy_info",
                    "info",
                    p,
                    f"CONVERGENCE_INFO: medium drift in {p} — {d} (class: {c})",
                    repo=repo_name,
                    ts=ts,
                )
            )

        # I-002: Low drift findings as info
        if s == "low":
            _a(
                _finding(
                    "I-002",
                    "policy_info",
                    "info",
                    p,
                    f"CONVERGENCE_INFO: low drift in {p} — {d} (class: {c})",
                    repo=repo_name,
                    ts=ts,
                )
            )

    # W-001: Any drift findings present trigger a warning
    if drift:
        _a(
            _finding(
                "W-001",
                "policy_warn",
                "medium",
                "",
                f"CONVERGENCE_WARN: repo {repo_name} has {len(drift)} drift findings",
                repo=repo_name,
                ts=ts,
            )
        )

    # W-002: Derivative repos that are not export-ready
    if repo_role == "derivative" and scan.get("export_ready") is False:
        _a(
            _finding(
                "W-002",
                "policy_warn",
                "medium",
                "",
                f"CONVERGENCE_WARN: derivative repo {repo_name} is not export-ready",
                repo=repo_name,
                ts=ts,
            )
        )

    return out


def _eval_derivation(sync: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate sot_opencore_derivation_policy.rego rules (D-001..D-005, W-001..W-005, I-001..I-004)."""
    out: list[dict[str, Any]] = []
    _a = out.append
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical_repo = sync.get("canonical_repo", "SSID")
    derivative_repo = sync.get("derivative_repo", "SSID-open-core")

    # D-005: Overall status FAIL is unconditional deny
    if sync.get("status") == "fail":
        _a(
            _finding(
                "D-005",
                "policy_deny",
                "critical",
                "",
                f"DERIVATION_DENY: overall sync status is FAIL for {canonical_repo} -> {derivative_repo}",
                repo=derivative_repo,
                ts=ts,
            )
        )

    for f in sync.get("findings", []):
        c = f.get("class", "")
        s = f.get("severity", "info")
        p = f.get("path", "")
        d = f.get("detail", "")

        # D-001: Forbidden export findings are unconditional deny
        if c == "forbidden_export":
            _a(
                _finding(
                    "D-001",
                    "policy_deny",
                    "critical",
                    p,
                    f"DERIVATION_DENY: forbidden artifact leaked to derivative — {d} (path: {p})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

        # D-002: Contract hash mismatch is unconditional deny
        if c == "contract_hash_mismatch":
            _a(
                _finding(
                    "D-002",
                    "policy_deny",
                    "critical",
                    p,
                    f"DERIVATION_DENY: contract hash mismatch — {d} (path: {p})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

        # D-003: Critical stale derivative bindings are denied
        if c == "stale_derivative_binding" and s == "critical":
            _a(
                _finding(
                    "D-003",
                    "policy_deny",
                    "critical",
                    p,
                    f"DERIVATION_DENY: critical stale derivative binding — {d} (path: {p})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

        # D-004: Export scope violations are denied
        if c == "export_scope_violation":
            _a(
                _finding(
                    "D-004",
                    "policy_deny",
                    "critical",
                    p,
                    f"DERIVATION_DENY: export scope violation — {d} (path: {p})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

        # W-001: Missing expected exports
        if c == "missing_expected_export":
            _a(
                _finding(
                    "W-001",
                    "policy_warn",
                    "medium",
                    p,
                    f"DERIVATION_WARN: expected public artifact missing from derivative — {d} (path: {p})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

        # W-002: Registry binding missing or inconsistent
        if c == "registry_binding_missing":
            _a(
                _finding(
                    "W-002",
                    "policy_warn",
                    "medium",
                    p,
                    f"DERIVATION_WARN: registry binding issue — {d} (path: {p})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

        # W-004: Non-critical stale derivative bindings
        if c == "stale_derivative_binding" and s != "critical":
            _a(
                _finding(
                    "W-004",
                    "policy_warn",
                    "medium",
                    p,
                    f"DERIVATION_WARN: stale derivative binding — {d} (path: {p}, severity: {s})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

        # W-005: Unsanctioned public artifacts
        if c == "unsanctioned_public_artifact":
            _a(
                _finding(
                    "W-005",
                    "policy_warn",
                    "medium",
                    p,
                    f"DERIVATION_WARN: unsanctioned artifact in derivative — {d} (path: {p})",
                    repo=derivative_repo,
                    ts=ts,
                )
            )

    # W-003: Registry binding status is inconsistent at manifest level
    if sync.get("registry_binding_status") == "inconsistent":
        _a(
            _finding(
                "W-003",
                "policy_warn",
                "medium",
                "",
                f"DERIVATION_WARN: registry bindings inconsistent between {canonical_repo} and {derivative_repo}",
                repo=derivative_repo,
                ts=ts,
            )
        )

    # I-001: Partial export readiness
    missing_exports = sync.get("missing_exports", [])
    forbidden_exports = sync.get("forbidden_exports", [])
    actual_exports = sync.get("actual_exports", [])
    allowed_exports = sync.get("allowed_exports", [])
    if missing_exports and not forbidden_exports:
        _a(
            _finding(
                "I-001",
                "policy_info",
                "info",
                "",
                f"DERIVATION_INFO: partial export — {len(actual_exports)} of "
                f"{len(allowed_exports)} allowed artifacts present in derivative",
                repo=derivative_repo,
                ts=ts,
            )
        )

    # I-002: Full export completeness achieved
    if not missing_exports and not forbidden_exports:
        _a(
            _finding(
                "I-002",
                "policy_info",
                "info",
                "",
                f"DERIVATION_INFO: full export completeness — all {len(allowed_exports)} allowed artifacts present",
                repo=derivative_repo,
                ts=ts,
            )
        )

    # I-003: Registry binding status is unknown
    if sync.get("registry_binding_status") == "unknown":
        _a(
            _finding(
                "I-003",
                "policy_info",
                "info",
                "",
                "DERIVATION_INFO: registry binding status unknown — canonical registry may be absent",
                repo=derivative_repo,
                ts=ts,
            )
        )

    # I-004: Derivation mode for audit record
    derivation_mode = sync.get("derivation_mode", "unknown")
    _a(
        _finding(
            "I-004",
            "policy_info",
            "info",
            "",
            f"DERIVATION_INFO: derivation mode is '{derivation_mode}' for {canonical_repo} -> {derivative_repo}",
            repo=derivative_repo,
            ts=ts,
        )
    )

    return out


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _step_scan(canonical: Path) -> dict[str, Any]:
    return scanner_scan(canonical_contract_path=_CONTRACT_REL, target_repo_root=str(canonical), repo_role="canonical")


def _step_manifest(scan: dict[str, Any]) -> str:
    return generate_manifest(scan)


def _step_opencore_sync(canonical: Path, derivative: Path) -> dict[str, Any]:
    return opencore_scan(canonical_root=str(canonical), derivative_root=str(derivative))


def _step_policy(scan: dict[str, Any], sync: dict[str, Any]) -> list[dict[str, Any]]:
    findings = _eval_convergence(scan) + _eval_derivation(sync)
    # Tag all policy findings with source for _normalize
    for f in findings:
        f.setdefault("source", "policy_engine")
    return findings


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _collect(scan: dict, sync: dict, policy: list) -> list[dict[str, Any]]:
    u: list[dict[str, Any]] = []
    for i, f in enumerate(scan.get("drift_findings", [])):
        u.append(_normalize(f, "scanner", i))
    for i, f in enumerate(sync.get("findings", [])):
        u.append(_normalize(f, "opencore_sync", i))
    for i, f in enumerate(policy):
        u.append(_normalize(f, "policy", i))
    return u


def _max_sev(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "info"
    return max((f["severity"] for f in findings), key=lambda s: _SEV_RANK.get(s, 0))


def _decide(findings: list[dict[str, Any]]) -> tuple[str, int]:
    if not findings:
        return "pass", EXIT_SUCCESS
    if any(f.get("class", "").startswith("policy_deny") or f["severity"] in ("critical", "high") for f in findings):
        return "fail", EXIT_DENY
    if any(f["severity"] in ("medium", "low") or f.get("class", "").startswith("policy_warn") for f in findings):
        return "warn", EXIT_WARN
    return "pass", EXIT_SUCCESS


def _run_identity(canonical: Path, derivative: Path, findings: list, decision: str, report_str: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    fh = [_sha256_str(json.dumps(f, sort_keys=True)) for f in findings]
    return {
        "run_id": str(uuid.uuid4()),
        "timestamp_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "contract_sha256": _sha256_file(canonical / _CONTRACT_REL),
        "contract_version": _contract_version(canonical / _CONTRACT_REL),
        "canonical_commit": _git_head(canonical),
        "derivative_commit": _git_head(derivative),
        "report_sha256": _sha256_str(report_str),
        "evidence_sha256": _sha256_str("".join(fh) or "no_findings"),
        "decision": decision,
    }


def _json_report(
    scan: dict, manifest: str, sync: dict, findings: list, decision: str, exit_code: int, rid: dict
) -> dict[str, Any]:
    lbl = {EXIT_SUCCESS: "success", EXIT_WARN: "warn", EXIT_DENY: "deny", EXIT_SYSTEM_ERROR: "system_error"}.get(
        exit_code, "unknown"
    )
    return {
        "report_version": "2.0.0",
        "run_identity": rid,
        "generated_at_utc": rid["timestamp_utc"],
        "pipeline_steps": ["scan", "manifest", "opencore_sync", "policy_check", "report"],
        "exit_code": exit_code,
        "exit_label": lbl,
        "decision": decision,
        "summary": {
            "total_findings": len(findings),
            "max_severity": _max_sev(findings),
            "scanner_status": scan.get("status", "UNKNOWN"),
            "opencore_sync_status": sync.get("status", "unknown"),
        },
        "findings": findings,
        "scanner_result": scan,
        "opencore_sync_result": sync,
    }


def _md_report(rpt: dict[str, Any], scan: dict[str, Any]) -> str:
    lines: list[str] = []
    s, lbl, rid = rpt["summary"], rpt["exit_label"].upper(), rpt["run_identity"]
    lines += [
        f"# SoT Convergence Report -- {lbl}",
        "",
        f"Generated: {rpt['generated_at_utc']}",
        f"Decision: **{rpt['decision']}**",
        "",
        "## Run Identity",
        "",
        "| Field | Value |",
        "|-------|-------|",
    ]
    lines += [f"| {k} | `{v}` |" for k, v in rid.items()]
    lines += [
        "",
        "## Pipeline Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Exit code | `{rpt['exit_code']}` ({lbl}) |",
        f"| Total findings | {s['total_findings']} |",
        f"| Max severity | {s['max_severity']} |",
        f"| Scanner status | {s['scanner_status']} |",
        f"| OpenCore sync | {s['opencore_sync_status']} |",
        "",
        "## Scanner Details",
        "",
    ]
    lines += [l for l in render_report(scan).splitlines() if not l.startswith("# ")]
    ff = rpt.get("findings", [])
    if ff:
        lines += [
            "",
            "## Unified Findings",
            "",
            "| ID | Source | Class | Severity | Path | Details |",
            "|----|--------|-------|----------|------|---------|",
        ]
        lines += [
            f"| {f['id']} | {f['source']} | `{f['class']}` | {f['severity']} | `{f['path']}` | {f['details']} |"
            for f in ff
        ]
    else:
        lines += ["", "## Findings", "", "No findings. All convergence checks passed."]
    lines += ["", "---", f"*Generated by run_sot_convergence.py at {rpt['generated_at_utc']}*", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Unified SoT Convergence Validation Runner")
    p.add_argument("--canonical", required=True, help="Canonical SSID repo root")
    p.add_argument("--derivative", required=True, help="Derivative SSID-open-core repo root")
    p.add_argument("--manifest", default="export_sync_manifest.json")
    p.add_argument("--output-dir", required=True, help="Directory for output reports")
    return p


def run(args: argparse.Namespace) -> int:
    canonical, derivative = Path(args.canonical).resolve(), Path(args.derivative).resolve()
    output_dir = Path(args.output_dir).resolve()
    for label, d in [("canonical", canonical), ("derivative", derivative)]:
        if not d.is_dir():
            print(f"ERROR: {label} repo not found: {d}", file=sys.stderr)
            return EXIT_SYSTEM_ERROR
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] Running SoT convergence scan ...", file=sys.stderr)
    scan_result = _step_scan(canonical)

    print("[2/5] Generating convergence manifest ...", file=sys.stderr)
    try:
        manifest_json = _step_manifest(scan_result)
    except SchemaError as exc:
        print(f"Manifest schema error: {exc}", file=sys.stderr)
        manifest_json = json.dumps({"error": str(exc)}, indent=2)

    print("[3/5] Validating OpenCore derivation sync ...", file=sys.stderr)
    sync_result = _step_opencore_sync(canonical, derivative)

    print("[4/5] Running policy checks ...", file=sys.stderr)
    policy_findings = _step_policy(scan_result, sync_result)

    print("[5/5] Assembling reports ...", file=sys.stderr)
    findings = _collect(scan_result, sync_result, policy_findings)
    decision, exit_code = _decide(findings)

    rid = _run_identity(canonical, derivative, findings, decision, json.dumps(findings, sort_keys=True))
    report = _json_report(scan_result, manifest_json, sync_result, findings, decision, exit_code, rid)
    report_str = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    rid["report_sha256"] = _sha256_str(report_str)

    # JSON Schema validation before publish
    validation_errors = _validate_against_schema(report, _REPORT_SCHEMA)
    if validation_errors:
        err_detail = "; ".join(validation_errors)
        print(f"SCHEMA VALIDATION FAILED: {err_detail}", file=sys.stderr)
        audit_err = {
            "event_type": "schema_validation_failure",
            "errors": validation_errors,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (output_dir / "schema_error_audit.json").write_text(json.dumps(audit_err, indent=2) + "\n", encoding="utf-8")
        return EXIT_SYSTEM_ERROR

    # Write outputs
    (output_dir / "sot_convergence_report.json").write_text(report_str + "\n", encoding="utf-8")
    (output_dir / "sot_convergence_report.md").write_text(_md_report(report, scan_result), encoding="utf-8")
    (output_dir / "sot_convergence_report.sha256").write_text(
        f"{rid['evidence_sha256']}  sot_convergence_report.json\n", encoding="utf-8"
    )

    audit = {
        "event_type": "sot_convergence_run",
        "run_identity": rid,
        "decision": decision,
        "exit_code": exit_code,
        "total_findings": len(findings),
        "max_severity": _max_sev(findings),
        "policy_findings_count": len(policy_findings),
    }
    audit_path = output_dir / "run_audit_event.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for lbl, val in [
        ("JSON report", output_dir / "sot_convergence_report.json"),
        ("MD report", output_dir / "sot_convergence_report.md"),
        ("Audit event", audit_path),
        ("SHA-256", rid["evidence_sha256"]),
        ("Decision", decision),
        ("Exit code", f"{exit_code} ({report['exit_label']})"),
    ]:
        print(f"{lbl:12s}: {val}", file=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        sys.exit(run(args))
    except Exception:
        traceback.print_exc(file=sys.stderr)
        print("SYSTEM ERROR: pipeline aborted", file=sys.stderr)
        sys.exit(EXIT_SYSTEM_ERROR)


if __name__ == "__main__":
    main()
