#!/usr/bin/env python3
"""Report Aggregator — merges structured findings into a single convergence report.

Reads *.findings.json files from an input directory, aggregates all findings,
computes summary statistics, and writes JSON + Markdown output.

Usage:
    python report_aggregator.py --input-dir ./findings --output-dir ./reports \
        --run-id RUN_20260310 [--run-identity ./run_identity.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

PIPELINE_VERSION = "1.0.0"
_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_REPORT_SCHEMA = "sot_validation_report.schema.json"
_REPORT_REQUIRED = ("run_id", "timestamp_utc", "pipeline_version", "decision",
                    "summary", "findings")
SEVERITY_ORDER = {"deny": 0, "warn": 1, "info": 2}
REQUIRED_KEYS = {"id", "class", "severity", "source", "path", "details", "timestamp", "repo"}
RUN_IDENTITY_KEYS = {"run_id", "timestamp_utc", "contract_sha256",
                     "canonical_commit", "derivative_commit", "decision"}


def _validate_against_schema(data: dict, schema_name: str) -> list[str]:
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


def load_findings(input_dir: Path) -> list[dict]:
    """Load and merge all *.findings.json files from *input_dir*."""
    findings: list[dict] = []
    files = sorted(input_dir.glob("*.findings.json"))
    if not files:
        print(f"[warn] No *.findings.json files found in {input_dir}", file=sys.stderr)
        return findings
    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[error] Failed to read {fp.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, list):
            print(f"[error] {fp.name}: expected JSON array at root", file=sys.stderr)
            continue
        for item in data:
            if not REQUIRED_KEYS.issubset(item.keys()):
                missing = REQUIRED_KEYS - item.keys()
                print(f"[warn] {fp.name}: finding missing keys {missing}, skipped", file=sys.stderr)
                continue
            findings.append(item)
    return findings


def load_run_identity(path: Path) -> dict | None:
    """Load and validate a run-identity JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[error] Failed to read run-identity {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print("[error] run-identity: expected JSON object at root", file=sys.stderr)
        return None
    missing = RUN_IDENTITY_KEYS - data.keys()
    if missing:
        print(f"[warn] run-identity missing keys {missing}", file=sys.stderr)
    return data


def compute_evidence_sha256(findings: list[dict]) -> str:
    """Combined SHA-256 over all individual finding evidence_hash values."""
    h = hashlib.sha256()
    for f in sorted(findings, key=lambda x: x["id"]):
        h.update(f.get("evidence_hash", "").encode("utf-8"))
    return h.hexdigest()


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_stats(findings: list[dict]) -> dict:
    """Return summary counters by severity, class, source, and repo."""
    return {
        "total": len(findings),
        "by_severity": dict(Counter(f["severity"] for f in findings)),
        "by_class": dict(Counter(f["class"] for f in findings)),
        "by_source": dict(Counter(f["source"] for f in findings)),
        "by_repo": dict(Counter(f["repo"] for f in findings)),
    }


def decide_status(stats: dict) -> str:
    """PASS if zero deny findings, WARN if only warn/info, else FAIL."""
    if stats["by_severity"].get("deny", 0) > 0:
        return "FAIL"
    if stats["by_severity"].get("warn", 0) > 0:
        return "WARN"
    return "PASS"


def build_json_report(run_id: str, findings: list[dict], stats: dict,
                      status: str, ts: str, run_identity: dict | None = None,
                      evidence_sha256: str | None = None) -> dict:
    """Assemble the full JSON report payload."""
    report: dict = {}
    if run_identity:
        report["run_identity"] = {k: run_identity.get(k) for k in sorted(RUN_IDENTITY_KEYS)}
    report.update({
        "run_id": run_id, "timestamp_utc": ts, "pipeline_version": PIPELINE_VERSION,
        "decision": status, "summary": stats, "findings": findings,
    })
    if evidence_sha256:
        report["evidence_sha256"] = evidence_sha256
    return report


def write_audit_event(output_dir: Path, run_id: str, ts: str, status: str,
                      stats: dict, report_sha256: str, evidence_sha256: str) -> Path:
    """Write run_audit_event.json and return its path."""
    event = {
        "run_id": run_id, "timestamp": ts, "decision": status,
        "findings_summary": {
            "deny": stats["by_severity"].get("deny", 0),
            "warn": stats["by_severity"].get("warn", 0),
            "info": stats["by_severity"].get("info", 0),
            "total": stats["total"],
        },
        "report_sha256": report_sha256, "evidence_sha256": evidence_sha256,
    }
    out = output_dir / "run_audit_event.json"
    out.write_text(json.dumps(event, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _severity_sort_key(f: dict) -> tuple:
    return (SEVERITY_ORDER.get(f["severity"], 99), f["class"], f["path"])


def render_markdown(run_id: str, findings: list[dict], stats: dict, status: str,
                    ts: str, report_hash: str, evidence_hash: str,
                    run_identity: dict | None = None) -> str:
    """Render the Markdown convergence report."""
    lines: list[str] = ["# SoT Convergence Report", ""]
    # Run-Identity section
    if run_identity:
        lines += ["## Run Identity", "",
                  "| Field              | Value                                    |",
                  "|--------------------|------------------------------------------|"]
        for key in sorted(RUN_IDENTITY_KEYS):
            val = run_identity.get(key, "n/a")
            lines.append(f"| {key.replace('_', ' ').title():<19}| {str(val):<41}|")
        lines += ["", "---", ""]
    # Metadata
    lines += ["## Metadata", "",
              "| Field              | Value                        |",
              "|--------------------|------------------------------|",
              f"| Run-ID             | {run_id:<29}|",
              f"| Timestamp (UTC)    | {ts:<29}|",
              f"| Decision           | **{status}**{' ' * max(0, 25 - len(status))}|",
              f"| Pipeline Version   | {PIPELINE_VERSION:<29}|",
              "", "---", ""]
    # Summary
    deny_n = stats["by_severity"].get("deny", 0)
    warn_n = stats["by_severity"].get("warn", 0)
    info_n = stats["by_severity"].get("info", 0)
    lines += ["## Summary", "",
              f"- **Total Findings**: {stats['total']}",
              f"- **Deny**: {deny_n}", f"- **Warn**: {warn_n}", f"- **Info**: {info_n}",
              "", "---", ""]
    # Findings table
    lines += ["## Findings", ""]
    sorted_findings = sorted(findings, key=_severity_sort_key)
    if sorted_findings:
        lines += ["| # | Severity | Class | Source | Repo | Path | Details |",
                  "|---|----------|-------|--------|------|------|---------|"]
        for idx, f in enumerate(sorted_findings, 1):
            lines.append(f"| {idx} | {f['severity']} | {f['class']} | {f['source']} "
                         f"| {f['repo']} | `{f['path']}` | {f['details']} |")
    else:
        lines.append("> No findings.")
    lines += ["", "---", ""]
    # By Class
    lines += ["### Findings by Class", "", "| Class | Count |", "|-------|-------|"]
    for cls, cnt in sorted(stats["by_class"].items()):
        lines.append(f"| {cls} | {cnt} |")
    lines.append("")
    # By Source
    lines += ["### Findings by Source", "", "| Source | Count |", "|--------|-------|"]
    for src, cnt in sorted(stats["by_source"].items()):
        lines.append(f"| {src} | {cnt} |")
    lines += ["", "---", ""]
    # Evidence
    lines += ["## Evidence", "",
              "| Artifact            | SHA-256                                  |",
              "|---------------------|------------------------------------------|",
              f"| Report              | `{report_hash}` |",
              f"| Evidence (combined) | `{evidence_hash}` |", ""]
    evidence_findings = [f for f in findings if f.get("evidence_hash")]
    if evidence_findings:
        lines += ["### Finding Evidence Hashes", "",
                  "| Finding ID | Evidence SHA-256 |", "|------------|------------------|"]
        for f in evidence_findings:
            lines.append(f"| {f['id']} | `{f['evidence_hash']}` |")
        lines.append("")
    lines += ["---", ""]
    # Policy Evaluation
    lines += ["## Policy Evaluation", "",
              f"- Deny rules fired: {deny_n}", f"- Warn rules fired: {warn_n}",
              f"- Info rules fired: {info_n}", f"- Compliant: {status == 'PASS'}",
              "", "---", ""]
    # Audit Trail Reference
    lines += ["## Audit Trail", "",
              "Audit event written to `run_audit_event.json` in the output directory.",
              "", "---", "",
              f"*Generated by SSID Report Aggregator v{PIPELINE_VERSION}. Do not edit manually.*", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate *.findings.json into a convergence report.")
    parser.add_argument("--input-dir", required=True, type=Path, help="Directory with *.findings.json files")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for output reports")
    parser.add_argument("--run-id", required=True, help="Run identifier (e.g. RUN_20260310)")
    parser.add_argument("--run-identity", type=Path, default=None,
                        help="Optional JSON file with run identity metadata")
    args = parser.parse_args(argv)
    if not args.input_dir.is_dir():
        print(f"[error] Input directory does not exist: {args.input_dir}", file=sys.stderr)
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Load run identity (optional)
    run_identity: dict | None = None
    if args.run_identity:
        run_identity = load_run_identity(args.run_identity)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    findings = load_findings(args.input_dir)
    stats = compute_stats(findings)
    status = decide_status(stats)
    evidence_sha = compute_evidence_sha256(findings)
    # JSON report
    report_payload = build_json_report(args.run_id, findings, stats, status, ts,
                                       run_identity=run_identity, evidence_sha256=evidence_sha)
    # JSON Schema validation before writing
    schema_errors = _validate_against_schema(report_payload, _REPORT_SCHEMA)
    if schema_errors:
        err_detail = "; ".join(schema_errors)
        print(f"[error] SCHEMA VALIDATION FAILED: {err_detail}", file=sys.stderr)
        audit_err = {"event_type": "schema_validation_failure", "errors": schema_errors,
                     "timestamp": ts, "run_id": args.run_id}
        (args.output_dir / "schema_error_audit.json").write_text(
            json.dumps(audit_err, indent=2) + "\n", encoding="utf-8")
        return 3
    json_bytes = json.dumps(report_payload, indent=2, ensure_ascii=False).encode("utf-8")
    report_hash = sha256_of_bytes(json_bytes)
    report_payload["report_sha256"] = report_hash
    json_out = args.output_dir / "sot_convergence_report.json"
    json_out.write_bytes(json.dumps(report_payload, indent=2, ensure_ascii=False).encode("utf-8"))
    # Audit event
    audit_out = write_audit_event(args.output_dir, args.run_id, ts, status,
                                  stats, report_hash, evidence_sha)
    # Markdown report
    md_text = render_markdown(args.run_id, findings, stats, status, ts,
                              report_hash, evidence_sha, run_identity=run_identity)
    md_out = args.output_dir / "sot_convergence_report.md"
    md_out.write_text(md_text, encoding="utf-8")
    print(f"[{status}] {stats['total']} findings aggregated  (deny={stats['by_severity'].get('deny', 0)}, "
          f"warn={stats['by_severity'].get('warn', 0)}, info={stats['by_severity'].get('info', 0)})")
    print(f"  JSON  -> {json_out}")
    print(f"  MD    -> {md_out}")
    print(f"  Audit -> {audit_out}")
    print(f"  SHA   -> {report_hash}")
    return 0 if status != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
