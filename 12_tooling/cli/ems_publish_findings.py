#!/usr/bin/env python3
"""EMS Push – publishes SoT-Convergence findings to EMS /events/sot_validation.

Default: --dry-run. Use --no-dry-run to transmit.
# EMS /events/sot_validation ingest muss in SSID-EMS implementiert werden
# falls noch nicht vorhanden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import jsonschema

PIPELINE_VERSION = "1.0.0"
_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_EVENT_SCHEMA = "sot_validation_event.schema.json"
_EVENT_REQUIRED = (
    "event_type",
    "timestamp",
    "pipeline_version",
    "commit_id",
    "summary",
    "report_sha256",
    "findings_preview",
)
_EVENT_TYPES = ("sot_validation",)
REQUIRED_REPORT_FIELDS = ("findings",)
RUN_IDENTITY_FIELDS = ("run_id", "canonical_commit", "derivative_commit", "contract_sha256")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_report(report: dict) -> list[str]:
    """Return error messages for missing/invalid required fields."""
    errs: list[str] = []
    for f in REQUIRED_REPORT_FIELDS:
        if f not in report:
            errs.append(f"Missing required field: '{f}'")
    if "findings" in report and not isinstance(report["findings"], list):
        errs.append("'findings' must be a list")
    return errs


def _load_run_identity(path: Path) -> dict | None:
    """Load run-identity JSON; return extracted fields or None on error."""
    if not path.is_file():
        print(f"[ERR] Run-identity file not found: {path}", file=sys.stderr)
        return None
    try:
        data = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        print(f"[ERR] Invalid JSON in run-identity: {exc}", file=sys.stderr)
        return None
    return {k: data[k] for k in RUN_IDENTITY_FIELDS if k in data}


def _check_ems_health(base_url: str) -> bool:
    """Probe EMS /api/health to verify endpoint availability."""
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status < 300
    except (urllib.error.URLError, OSError):
        return False


def _build_payload(
    report: dict, report_raw: bytes, commit_id: str, manifest_hash: str, run_identity: dict | None = None
) -> dict:
    findings = report.get("findings", [])
    deny_c = sum(1 for f in findings if f.get("severity") == "deny")
    warn_c = sum(1 for f in findings if f.get("severity") == "warn")
    info_c = sum(1 for f in findings if f.get("severity") == "info")
    decision = "deny" if deny_c else ("warn" if warn_c else "pass")
    preview = findings[:10]
    for item in preview:
        for key in ("message", "detail"):
            if key in item and isinstance(item[key], str) and len(item[key]) > 256:
                item[key] = item[key][:253] + "..."
    payload: dict = {
        "event_type": "sot_validation",
        "timestamp": datetime.now(UTC).isoformat(),
        "pipeline_version": PIPELINE_VERSION,
        "commit_id": commit_id,
        "manifest_hash": manifest_hash,
        "summary": {
            "total_findings": len(findings),
            "deny_count": deny_c,
            "warn_count": warn_c,
            "info_count": info_c,
            "decision": decision,
        },
        "report_sha256": _sha256(report_raw),
        "evidence_sha256": report.get("evidence_sha256", ""),
        "findings_preview": preview,
    }
    if run_identity:
        payload["run_identity"] = run_identity
    return payload


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


def _validate_event_payload(payload: dict) -> list[str]:
    """Validate event payload against JSON Schema. Returns error strings."""
    return _validate_against_schema(payload, _EVENT_SCHEMA)


def _post_event(url: str, payload: dict, retries: int = 3) -> bool:
    """POST payload as JSON with exponential backoff."""
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status < 300:
                    print(f"[OK] EMS accepted event (HTTP {resp.status})")
                    return True
                print(f"[WARN] Unexpected status {resp.status}", file=sys.stderr)
        except urllib.error.HTTPError as exc:
            print(f"[ERR] Attempt {attempt}/{retries}: HTTP {exc.code} – {exc.reason}", file=sys.stderr)
        except (urllib.error.URLError, OSError) as exc:
            print(f"[ERR] Attempt {attempt}/{retries}: {exc}", file=sys.stderr)
        if attempt < retries:
            wait = 2 ** (attempt - 1)
            print(f"  retrying in {wait}s …", file=sys.stderr)
            time.sleep(wait)
    return False


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publish SoT-Convergence findings to EMS backend.")
    p.add_argument("--report", required=True, help="Path to sot_convergence_report.json")
    p.add_argument("--ems-url", default="http://localhost:8000", help="EMS backend base URL")
    p.add_argument("--commit-id", required=True, help="Git commit SHA that was validated")
    p.add_argument("--manifest-hash", default="", help="SHA-256 of integrity manifest (auto-derived if omitted)")
    p.add_argument("--run-identity", default=None, help="Path to run-identity JSON (run_id, canonical_commit, etc.)")
    dry = p.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run", dest="dry_run", action="store_true", default=True, help="Print payload without sending (default)"
    )
    dry.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Actually POST the event to EMS")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"[ERR] Report not found: {report_path}", file=sys.stderr)
        return 1
    report_raw = report_path.read_bytes()
    try:
        report = json.loads(report_raw)
    except json.JSONDecodeError as exc:
        print(f"[ERR] Invalid JSON in report: {exc}", file=sys.stderr)
        return 1
    # Validate required report fields
    for err in _validate_report(report):
        print(f"[ERR] Report validation: {err}", file=sys.stderr)
        return 1
    # Load optional run-identity
    run_identity: dict | None = None
    if args.run_identity:
        run_identity = _load_run_identity(Path(args.run_identity))
        if run_identity is None:
            return 1
    manifest_hash = args.manifest_hash or report.get("manifest_hash", _sha256(report_raw))
    payload = _build_payload(report, report_raw, args.commit_id, manifest_hash, run_identity)
    # JSON Schema validation before publish
    schema_errors = _validate_event_payload(payload)
    if schema_errors:
        err_detail = "; ".join(schema_errors)
        print(f"[ERR] SCHEMA VALIDATION FAILED: {err_detail}", file=sys.stderr)
        for err in schema_errors:
            print(f"[ERR]   - {err}", file=sys.stderr)
        # Write audit event about the schema failure
        audit_err = {
            "event_type": "schema_validation_failure",
            "schema": _EVENT_SCHEMA,
            "errors": schema_errors,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        audit_path = report_path.parent / "schema_error_audit.json"
        audit_path.write_text(json.dumps(audit_err, indent=2) + "\n", encoding="utf-8")
        print(f"[ERR] Audit event written to {audit_path}", file=sys.stderr)
        return 1
    if args.dry_run:
        print("[DRY-RUN] Would POST to:", f"{args.ems_url.rstrip('/')}/events/sot_validation")
        print(json.dumps(payload, indent=2))
        return 0
    # EMS health check before sending
    if not _check_ems_health(args.ems_url):
        print("[ERR] EMS endpoint not available, see PR-7 for history integration", file=sys.stderr)
        return 1
    endpoint = f"{args.ems_url.rstrip('/')}/events/sot_validation"
    print(f"[INFO] Posting event to {endpoint}")
    if _post_event(endpoint, payload):
        return 0
    print("[ERR] All retries exhausted – event not delivered", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
