#!/usr/bin/env python3
"""
Registry Canonicalization Gate — validates sot_registry.json integrity.
Checks file existence, SHA256 hashes, format consistency, evidence refs.
Produces: JSON findings, MD report, PASS/WARN/DENY exit code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

# ---------------------------------------------------------------------------
# SOT_ALLOWLIST — canonical artifact set (mirrored from sot_registry_build.py)
# ---------------------------------------------------------------------------
SOT_ALLOWLIST: list[dict[str, str]] = [
    {"name": "sot_validator_core", "path": "03_core/validators/sot/sot_validator_core.py"},
    {"name": "sot_policy_rego", "path": "23_compliance/policies/sot/sot_policy.rego"},
    {"name": "sot_contract_yaml", "path": "16_codex/contracts/sot/sot_contract.yaml"},
    {"name": "sot_validator_cli", "path": "12_tooling/cli/sot_validator.py"},
    {"name": "sot_tests", "path": "11_test_simulation/tests_compliance/test_sot_validator.py"},
    {"name": "sot_audit_report", "path": "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md"},
    {"name": "sot_diff_alert", "path": "02_audit_logging/reports/SOT_DIFF_ALERT.json"},
    {"name": "gate_runner", "path": "12_tooling/cli/run_all_gates.py"},
    {"name": "structure_spec", "path": "24_meta_orchestration/registry/structure_spec.json"},
    {"name": "sot_diff_alert_generator", "path": "12_tooling/cli/sot_diff_alert.py"},
]

REGISTRY_REL = "24_meta_orchestration/registry/sot_registry.json"
REPORT_REL = "02_audit_logging/reports"

# Exit codes
EXIT_PASS = 0
EXIT_WARN = 1
EXIT_DENY = 2
EXIT_ERROR = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_repo_root() -> Path:
    """Auto-detect repo root via git or fallback to file-relative."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return Path(__file__).resolve().parents[2]


def _sha256_file(filepath: Path) -> str | None:
    """SHA256 hex digest of file. Returns None if missing."""
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except (FileNotFoundError, OSError):
        return None


def _sha256_string(s: str) -> str:
    """SHA256 hex digest of a string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _finding_id(finding_class: str, path: str) -> str:
    """Generate finding ID: REG_CANON-{class}-{hash8}."""
    h8 = _sha256_string(path)[:8]
    return f"REG_CANON-{finding_class}-{h8}"


def _normalize_hash(raw: str) -> str:
    """Strip 'sha256:' prefix if present, return lowercase hex."""
    if raw.startswith("sha256:"):
        return raw[7:].lower().strip()
    return raw.lower().strip()


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def run_canonicalization(
    repo_root: Path,
    output_dir: Path,
    strict: bool = False,
) -> Dict[str, Any]:
    """Run full registry canonicalization check. Returns structured result."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry_path = repo_root / REGISTRY_REL
    findings: List[Dict[str, Any]] = []

    # --- Load registry ---
    if not registry_path.is_file():
        findings.append({
            "id": _finding_id("missing_file", REGISTRY_REL),
            "class": "missing_file",
            "severity": "deny",
            "source": "registry_canonicalization",
            "path": REGISTRY_REL,
            "details": "sot_registry.json not found on disk",
            "timestamp_utc": ts,
            "repo": str(repo_root),
        })
        return _build_result(ts, repo_root, findings)

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        findings.append({
            "id": _finding_id("parse_error", REGISTRY_REL),
            "class": "parse_error",
            "severity": "deny",
            "source": "registry_canonicalization",
            "path": REGISTRY_REL,
            "details": f"Failed to parse sot_registry.json: {exc}",
            "timestamp_utc": ts,
            "repo": str(repo_root),
        })
        return _build_result(ts, repo_root, findings)

    artifacts = registry.get("roots", {}).get("sot_artifacts", [])

    # --- Per-artifact checks ---
    registered_paths: set[str] = set()

    for art in artifacts:
        art_path = art.get("path", "")
        art_name = art.get("name", "unknown")
        art_hash = art.get("hash_sha256", "")
        registered_paths.add(art_path)

        full_path = repo_root / art_path

        # 1. File existence
        if not full_path.is_file():
            findings.append({
                "id": _finding_id("missing_file", art_path),
                "class": "missing_file",
                "severity": "deny",
                "source": "registry_canonicalization",
                "path": art_path,
                "details": f"Artifact '{art_name}' not found on disk",
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })
            continue

        # 2. Hash computation and comparison
        current_hash = _sha256_file(full_path)
        normalized_registry_hash = _normalize_hash(art_hash)

        # 2a. Format consistency check (sha256: prefix)
        if art_hash.startswith("sha256:"):
            findings.append({
                "id": _finding_id("format_inconsistency", art_path),
                "class": "format_inconsistency",
                "severity": "warn",
                "source": "registry_canonicalization",
                "path": art_path,
                "details": f"Hash has 'sha256:' prefix — raw hex expected",
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })

        # 2b. Hash mismatch
        if current_hash and current_hash != normalized_registry_hash:
            findings.append({
                "id": _finding_id("hash_mismatch", art_path),
                "class": "hash_mismatch",
                "severity": "deny",
                "source": "registry_canonicalization",
                "path": art_path,
                "details": (
                    f"SHA256 mismatch for '{art_name}': "
                    f"registry={normalized_registry_hash[:16]}... "
                    f"disk={current_hash[:16]}..."
                ),
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })

        # 3. evidence_ref check
        if "evidence_ref" not in art:
            findings.append({
                "id": _finding_id("missing_evidence_ref", art_path),
                "class": "missing_evidence_ref",
                "severity": "warn",
                "source": "registry_canonicalization",
                "path": art_path,
                "details": f"Artifact '{art_name}' has no evidence_ref field",
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })

        # 4. Strict mode: check for unknown fields
        if strict:
            known_fields = {"name", "path", "hash_sha256", "evidence_ref", "source_of_truth_ref"}
            unknown = set(art.keys()) - known_fields
            if unknown:
                findings.append({
                    "id": _finding_id("unknown_fields", art_path),
                    "class": "unknown_fields",
                    "severity": "deny",
                    "source": "registry_canonicalization",
                    "path": art_path,
                    "details": f"Unknown fields in artifact '{art_name}': {sorted(unknown)}",
                    "timestamp_utc": ts,
                    "repo": str(repo_root),
                })

    # --- Unregistered artifact scan (SOT_ALLOWLIST vs registry) ---
    for allowed in SOT_ALLOWLIST:
        if allowed["path"] not in registered_paths:
            disk_path = repo_root / allowed["path"]
            if disk_path.is_file():
                findings.append({
                    "id": _finding_id("unregistered_artifact", allowed["path"]),
                    "class": "unregistered_artifact",
                    "severity": "warn",
                    "source": "registry_canonicalization",
                    "path": allowed["path"],
                    "details": (
                        f"Artifact '{allowed['name']}' exists on disk "
                        f"but is not in sot_registry.json"
                    ),
                    "timestamp_utc": ts,
                    "repo": str(repo_root),
                })

    return _build_result(ts, repo_root, findings)


def _build_result(
    ts: str,
    repo_root: Path,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build structured result from findings."""
    deny_count = sum(1 for f in findings if f["severity"] == "deny")
    warn_count = sum(1 for f in findings if f["severity"] == "warn")

    if deny_count > 0:
        status = "DENY"
    elif warn_count > 0:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "gate": "registry_canonicalization",
        "version": "1.0.0",
        "timestamp_utc": ts,
        "status": status,
        "repo": str(repo_root),
        "summary": {
            "total_findings": len(findings),
            "deny": deny_count,
            "warn": warn_count,
        },
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _findings_to_json(result: Dict[str, Any]) -> str:
    """Render findings as JSON string."""
    return json.dumps(result, indent=2, sort_keys=False)


def _findings_to_md(result: Dict[str, Any]) -> str:
    """Render findings as Markdown report."""
    lines = [
        "# Registry Canonicalization Report\n",
        f"\nTimestamp: {result['timestamp_utc']}\n",
        f"Status: **{result['status']}**\n",
        f"Total findings: {result['summary']['total_findings']}\n",
        f"Deny: {result['summary']['deny']}\n",
        f"Warn: {result['summary']['warn']}\n",
    ]

    if result["findings"]:
        lines.append("\n## Findings\n")
        lines.append("\n| ID | Severity | Path | Details |\n")
        lines.append("|----|----------|------|---------|\n")
        for f in result["findings"]:
            lines.append(
                f"| `{f['id']}` | {f['severity']} "
                f"| `{f['path']}` | {f['details']} |\n"
            )
    else:
        lines.append("\nNo findings — all registry artifacts are canonical.\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Run-ledger builder
# ---------------------------------------------------------------------------

def _build_run_ledger(
    result: Dict[str, Any],
    gate_type: str,
    repo_root: Path,
    related_repo: str = "",
    trigger: str = "manual",
) -> Dict[str, Any]:
    """Build a run-ledger dict from a gate result."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = (
        f"{gate_type}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"_{uuid4().hex[:8]}"
    )

    # Detect CI vs manual
    if any(os.environ.get(v) for v in ("CI", "GITHUB_ACTIONS", "GITLAB_CI")):
        trigger = "ci"

    # Derive exit_code from status
    status = result.get("status", "PASS").upper()
    exit_code_map = {"PASS": EXIT_PASS, "WARN": EXIT_WARN, "DENY": EXIT_DENY}
    exit_code = exit_code_map.get(status, EXIT_ERROR)

    # Extract unique artifact paths from findings
    artifacts = sorted({f.get("path", "") for f in result.get("findings", []) if f.get("path")})

    # Extract evidence_refs and source_of_truth_refs from findings
    evidence_refs = sorted({
        f["evidence_ref"]
        for f in result.get("findings", [])
        if isinstance(f.get("evidence_ref"), str) and f["evidence_ref"]
    })
    source_of_truth_refs = sorted({
        f["source_of_truth_ref"]
        for f in result.get("findings", [])
        if isinstance(f.get("source_of_truth_ref"), str) and f["source_of_truth_ref"]
    })

    # Commit SHA
    commit_sha = ""
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if cp.returncode == 0:
            commit_sha = cp.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # PR number from env
    pr_raw = os.environ.get("PR_NUMBER", "")
    pr_number: int | None = int(pr_raw) if pr_raw.isdigit() else None

    return {
        "run_id": run_id,
        "gate_type": gate_type,
        "repo": str(repo_root),
        "related_repo": str(related_repo) if related_repo else "",
        "trigger": trigger,
        "started_at": result.get("timestamp_utc", now_utc),
        "finished_at": now_utc,
        "decision": result.get("status", "PASS").lower(),
        "severity_summary": result.get("summary", {}),
        "findings_count": len(result.get("findings", [])),
        "findings": result.get("findings", []),
        "artifacts": artifacts,
        "registry_refs": ["24_meta_orchestration/registry/sot_registry.json"],
        "evidence_refs": evidence_refs,
        "source_of_truth_refs": source_of_truth_refs,
        "exit_code": exit_code,
        "correlation_id": os.environ.get("GATE_CORRELATION_ID", ""),
        "parent_run_id": os.environ.get("GATE_PARENT_RUN_ID", ""),
        "commit_sha": commit_sha,
        "pr_number": pr_number,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_registry_canonicalization",
        description="Registry Canonicalization Gate — validate sot_registry.json integrity",
    )
    parser.add_argument(
        "--repo-root", type=str, default=None,
        help="Path to SSID repo root (default: auto-detect via git)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help=f"Report output directory (default: <repo-root>/{REPORT_REL})",
    )
    parser.add_argument(
        "--write-reports", action="store_true",
        help="Write JSON + MD reports to output directory",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Verify only — print result, no reports written",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Strict mode: unknown fields in artifacts = deny",
    )
    parser.add_argument(
        "--emit-run-ledger", action="store_true",
        help="Write a *_run_ledger.json to output directory",
    )
    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(args.repo_root).resolve() if args.repo_root else _detect_repo_root()
    output_dir = Path(args.output_dir) if args.output_dir else repo_root / REPORT_REL

    if not repo_root.is_dir():
        print(f"ERROR: repo-root not found: {repo_root}", file=sys.stderr)
        return EXIT_ERROR

    # Run canonicalization
    try:
        result = run_canonicalization(repo_root, output_dir, strict=args.strict)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Print summary
    print(
        f"REGISTRY_CANON: {result['status']} "
        f"(findings: {result['summary']['total_findings']}, "
        f"deny: {result['summary']['deny']}, "
        f"warn: {result['summary']['warn']})"
    )
    for f in result["findings"]:
        severity_tag = "DENY" if f["severity"] == "deny" else "WARN"
        print(f"  {severity_tag}: {f['id']}: {f['details']}")

    # Write reports (unless --verify-only)
    if args.write_reports and not args.verify_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "registry_canonicalization_findings.json"
        md_path = output_dir / "registry_canonicalization_report.md"
        json_path.write_text(_findings_to_json(result), encoding="utf-8")
        md_path.write_text(_findings_to_md(result), encoding="utf-8")
        print(f"REPORT: {json_path}")
        print(f"REPORT: {md_path}")

    # Emit run ledger
    if args.emit_run_ledger and not args.verify_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        ledger = _build_run_ledger(result, "registry_canonicalization", repo_root)
        ledger_path = output_dir / "registry_canonicalization_run_ledger.json"
        ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        print(f"LEDGER: {ledger_path}")

    # Exit code
    if result["status"] == "DENY":
        return EXIT_DENY
    elif result["status"] == "WARN":
        return EXIT_WARN
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
