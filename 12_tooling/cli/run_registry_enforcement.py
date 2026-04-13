#!/usr/bin/env python3
"""
Registry Enforcement Gate — full Disk / Registry / Evidence / SoT-Ref reconciliation.

Performs cross-validation of:
- Disk artifacts vs. sot_registry.json entries
- SHA256 integrity hashes
- evidence_ref completeness and validity
- source_of_truth_ref presence for SoT/Policy/Validator artifacts
- Duplicate detection (artifact IDs and paths)
- Fail-open guard detection in validators

Produces: registry_enforcement_findings.json, registry_enforcement_report.md
Exit codes: 0=PASS, 1=WARN, 2=DENY, 3=ERROR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
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

# Phase-1 enforced directory scopes (relative to repo root)
ENFORCED_SCOPES: list[dict[str, str]] = [
    {"prefix": "23_compliance/policies/", "artifact_type": "policy"},
    {"prefix": "03_core/validators/", "artifact_type": "validator"},
    {"prefix": "12_tooling/cli/", "artifact_type": "cli_tool"},
    {"prefix": "02_audit_logging/reports/", "artifact_type": "report"},
    {"prefix": "24_meta_orchestration/registry/", "artifact_type": "schema"},
]

# Artifacts that MUST have source_of_truth_ref
SOT_REF_REQUIRED_PREFIXES = [
    "03_core/validators/",
    "23_compliance/policies/",
    "24_meta_orchestration/registry/",
]

REGISTRY_REL = "24_meta_orchestration/registry/sot_registry.json"
REPORT_REL = "02_audit_logging/reports"

# Exit codes
EXIT_PASS = 0
EXIT_WARN = 1
EXIT_DENY = 2
EXIT_ERROR = 3

# Fail-open detection patterns
_FAIL_OPEN_PATTERNS = [
    re.compile(r"""(?:pass|skip|continue|return\s+(?:True|None|0|"pass"|'pass'))"""),
]
_FAIL_OPEN_CONTEXT = re.compile(
    r"(?:except|else|default|unknown|_|\*)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Normalization (inlined — cross-repo import not possible)
# Based on SSID-EMS/src/ssidctl/schemas/registry_normalizer.py
# ---------------------------------------------------------------------------
_SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
_SHA256_PREFIX = "sha256:"


def _normalize_sha256(value: str) -> str:
    """Normalize SHA256 to raw 64-char hex. Strips 'sha256:' prefix."""
    raw = value.lower().strip()
    if raw.startswith(_SHA256_PREFIX):
        raw = raw[len(_SHA256_PREFIX):]
    return raw


def _is_valid_sha256(value: str) -> bool:
    """Check if value is valid 64-char hex SHA256."""
    return bool(_SHA256_HEX_RE.match(value))


def _normalize_evidence_ref(value: Any) -> dict[str, str]:
    """Normalize evidence_ref to canonical object format."""
    if value is None:
        return {"type": "none", "hash": "", "path": ""}
    if isinstance(value, str):
        return {"type": "path", "hash": "", "path": value}
    if isinstance(value, dict):
        ref_hash = value.get("hash", "") or ""
        if ref_hash:
            ref_hash = _normalize_sha256(ref_hash)
        return {
            "type": value.get("type", "path"),
            "hash": ref_hash,
            "path": value.get("path", ""),
        }
    return {"type": "unknown", "hash": "", "path": ""}


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
    """Generate finding ID: REG_ENF-{class}-{hash8}."""
    h8 = _sha256_string(path)[:8]
    return f"REG_ENF-{finding_class}-{h8}"


def _normalize_hash(raw: str) -> str:
    """Strip 'sha256:' prefix if present, return lowercase hex."""
    if raw.startswith("sha256:"):
        return raw[7:].lower().strip()
    return raw.lower().strip()


def _classify_artifact(path: str) -> str:
    """Determine artifact_type from path."""
    for scope in ENFORCED_SCOPES:
        if path.startswith(scope["prefix"]):
            return scope["artifact_type"]
    return "sot_artifact"


def _is_in_enforced_scope(path: str) -> bool:
    """Check if path falls within Phase-1 enforced scopes."""
    for scope in ENFORCED_SCOPES:
        if path.startswith(scope["prefix"]):
            return True
    # Also check SOT_ALLOWLIST paths explicitly
    for entry in SOT_ALLOWLIST:
        if path == entry["path"]:
            return True
    return False


def _requires_sot_ref(path: str) -> bool:
    """Check if artifact requires source_of_truth_ref."""
    for prefix in SOT_REF_REQUIRED_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _check_fail_open(filepath: Path) -> list[tuple[int, str]]:
    """Scan a validator/guard file for fail-open patterns.

    Returns list of (line_number, line_text) where fail-open is suspected.
    Only checks .py files.
    """
    if filepath.suffix != ".py":
        return []
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Look for except/else/default blocks that pass/skip/continue
        if _FAIL_OPEN_CONTEXT.search(stripped):
            # Check following lines (up to 3) for fail-open action
            for j in range(i, min(i + 4, len(lines) + 1)):
                check_line = lines[j - 1].strip()
                for pattern in _FAIL_OPEN_PATTERNS:
                    if pattern.search(check_line):
                        hits.append((j, check_line))
    return hits


# ---------------------------------------------------------------------------
# Core enforcement logic
# ---------------------------------------------------------------------------

def run_enforcement(
    repo_root: Path,
    output_dir: Path,
    strict: bool = False,
    verify_only: bool = False,
) -> Dict[str, Any]:
    """Run full registry enforcement check. Returns structured result."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry_path = repo_root / REGISTRY_REL
    findings: List[Dict[str, Any]] = []

    # --- Check 0: Registry parseable ---
    if not registry_path.is_file():
        findings.append({
            "id": _finding_id("registry_schema_invalid", REGISTRY_REL),
            "class": "registry_schema_invalid",
            "severity": "deny",
            "source": "registry_enforcement",
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
            "id": _finding_id("registry_schema_invalid", REGISTRY_REL),
            "class": "registry_schema_invalid",
            "severity": "deny",
            "source": "registry_enforcement",
            "path": REGISTRY_REL,
            "details": f"Failed to parse sot_registry.json: {exc}",
            "timestamp_utc": ts,
            "repo": str(repo_root),
        })
        return _build_result(ts, repo_root, findings)

    artifacts = registry.get("roots", {}).get("sot_artifacts", [])

    # --- Check 1: Duplicate detection ---
    seen_names: Dict[str, str] = {}  # name -> first path
    seen_paths: Dict[str, str] = {}  # path -> first name

    for art in artifacts:
        art_name = art.get("name", "")
        art_path = art.get("path", "")

        # Duplicate artifact ID/name
        if art_name in seen_names:
            findings.append({
                "id": _finding_id("duplicate_artifact_id", art_path),
                "class": "duplicate_artifact_id",
                "severity": "deny",
                "source": "registry_enforcement",
                "path": art_path,
                "details": (
                    f"Duplicate artifact name '{art_name}' — "
                    f"also registered at '{seen_names[art_name]}'"
                ),
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })
        else:
            seen_names[art_name] = art_path

        # Duplicate path
        if art_path in seen_paths:
            findings.append({
                "id": _finding_id("duplicate_path", art_path),
                "class": "duplicate_path",
                "severity": "deny",
                "source": "registry_enforcement",
                "path": art_path,
                "details": (
                    f"Duplicate path '{art_path}' — "
                    f"also registered as '{seen_paths[art_path]}'"
                ),
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })
        else:
            seen_paths[art_path] = art_name

    # --- Check 2: Per-artifact enforcement ---
    registered_paths: Set[str] = set()

    for art in artifacts:
        art_path = art.get("path", "")
        art_name = art.get("name", "unknown")
        art_hash = art.get("hash_sha256", "")
        registered_paths.add(art_path)

        # Skip artifacts outside Phase-1 scope
        if not _is_in_enforced_scope(art_path):
            continue

        full_path = repo_root / art_path

        # 2a. Orphan registry entry (file missing on disk)
        if not full_path.is_file():
            findings.append({
                "id": _finding_id("orphan_registry_entry", art_path),
                "class": "orphan_registry_entry",
                "severity": "deny",
                "source": "registry_enforcement",
                "path": art_path,
                "details": (
                    f"Registry entry '{art_name}' has no corresponding "
                    f"file on disk"
                ),
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })
            continue

        # 2b. Hash mismatch
        if art_hash:
            current_hash = _sha256_file(full_path)
            normalized_registry_hash = _normalize_hash(art_hash)
            if current_hash and current_hash != normalized_registry_hash:
                findings.append({
                    "id": _finding_id("hash_mismatch", art_path),
                    "class": "hash_mismatch",
                    "severity": "deny",
                    "source": "registry_enforcement",
                    "path": art_path,
                    "details": (
                        f"SHA256 mismatch for '{art_name}': "
                        f"registry={normalized_registry_hash[:16]}... "
                        f"disk={current_hash[:16]}..."
                    ),
                    "timestamp_utc": ts,
                    "repo": str(repo_root),
                })

        # 2c. Missing evidence_ref (deny, not warn)
        if "evidence_ref" not in art:
            findings.append({
                "id": _finding_id("missing_evidence_ref", art_path),
                "class": "missing_evidence_ref",
                "severity": "deny",
                "source": "registry_enforcement",
                "path": art_path,
                "details": (
                    f"Artifact '{art_name}' has no evidence_ref field"
                ),
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })
        else:
            # 2d. Invalid evidence_ref
            ref = _normalize_evidence_ref(art.get("evidence_ref"))
            ref_hash = ref.get("hash", "")
            ref_path = ref.get("path", "")
            if not ref_hash and not ref_path:
                findings.append({
                    "id": _finding_id("invalid_evidence_ref", art_path),
                    "class": "invalid_evidence_ref",
                    "severity": "deny",
                    "source": "registry_enforcement",
                    "path": art_path,
                    "details": (
                        f"Artifact '{art_name}' has evidence_ref but "
                        f"it contains neither hash nor path"
                    ),
                    "timestamp_utc": ts,
                    "repo": str(repo_root),
                })
            elif ref_hash and not _is_valid_sha256(ref_hash):
                findings.append({
                    "id": _finding_id("invalid_evidence_ref", art_path),
                    "class": "invalid_evidence_ref",
                    "severity": "deny",
                    "source": "registry_enforcement",
                    "path": art_path,
                    "details": (
                        f"Artifact '{art_name}' has evidence_ref with "
                        f"invalid hash format"
                    ),
                    "timestamp_utc": ts,
                    "repo": str(repo_root),
                })

        # 2e. Missing source_of_truth_ref for SoT/Policy/Validator artifacts
        if _requires_sot_ref(art_path) and "source_of_truth_ref" not in art:
            findings.append({
                "id": _finding_id("missing_source_of_truth_ref", art_path),
                "class": "missing_source_of_truth_ref",
                "severity": "deny",
                "source": "registry_enforcement",
                "path": art_path,
                "details": (
                    f"Artifact '{art_name}' is a SoT/Policy/Validator "
                    f"artifact but has no source_of_truth_ref"
                ),
                "timestamp_utc": ts,
                "repo": str(repo_root),
            })

        # 2f. Fail-open guard detection (validators and CLI gates)
        if art_path.startswith("03_core/validators/") or (
            art_path.startswith("12_tooling/cli/") and art_path.endswith(".py")
        ):
            fail_open_hits = _check_fail_open(full_path)
            if fail_open_hits:
                hit_summary = "; ".join(
                    f"L{ln}: {txt[:60]}" for ln, txt in fail_open_hits[:3]
                )
                findings.append({
                    "id": _finding_id("fail_open_guard", art_path),
                    "class": "fail_open_guard",
                    "severity": "deny",
                    "source": "registry_enforcement",
                    "path": art_path,
                    "details": (
                        f"Potential fail-open in '{art_name}': "
                        f"{len(fail_open_hits)} hit(s) — {hit_summary}"
                    ),
                    "timestamp_utc": ts,
                    "repo": str(repo_root),
                })

    # --- Check 3: Unregistered artifacts (on disk but not in registry) ---
    for allowed in SOT_ALLOWLIST:
        if allowed["path"] not in registered_paths:
            disk_path = repo_root / allowed["path"]
            if disk_path.is_file():
                findings.append({
                    "id": _finding_id("unregistered_artifact", allowed["path"]),
                    "class": "unregistered_artifact",
                    "severity": "deny",
                    "source": "registry_enforcement",
                    "path": allowed["path"],
                    "details": (
                        f"Artifact '{allowed['name']}' exists on disk "
                        f"in SOT_ALLOWLIST but is not in sot_registry.json"
                    ),
                    "timestamp_utc": ts,
                    "repo": str(repo_root),
                })

    # --- Check 4 (strict): Scan enforced scope dirs for untracked files ---
    if strict:
        for scope in ENFORCED_SCOPES:
            scope_dir = repo_root / scope["prefix"]
            if not scope_dir.is_dir():
                continue
            for fpath in scope_dir.rglob("*"):
                if not fpath.is_file():
                    continue
                rel = fpath.relative_to(repo_root).as_posix()
                if rel not in registered_paths:
                    findings.append({
                        "id": _finding_id("unregistered_artifact", rel),
                        "class": "unregistered_artifact",
                        "severity": "deny",
                        "source": "registry_enforcement",
                        "path": rel,
                        "details": (
                            f"File '{rel}' in enforced scope "
                            f"'{scope['prefix']}' is not in registry"
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
    info_count = sum(1 for f in findings if f["severity"] == "info")

    if deny_count > 0:
        status = "DENY"
    elif warn_count > 0:
        status = "WARN"
    else:
        status = "PASS"

    # Group findings by class for summary
    by_class: Dict[str, int] = {}
    for f in findings:
        cls = f["class"]
        by_class[cls] = by_class.get(cls, 0) + 1

    return {
        "gate": "registry_enforcement",
        "version": "1.0.0",
        "timestamp_utc": ts,
        "status": status,
        "repo": str(repo_root),
        "summary": {
            "total_findings": len(findings),
            "deny": deny_count,
            "warn": warn_count,
            "info": info_count,
            "by_class": by_class,
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
        "# Registry Enforcement Report\n",
        f"\nTimestamp: {result['timestamp_utc']}\n",
        f"Status: **{result['status']}**\n",
        f"Total findings: {result['summary']['total_findings']}\n",
        f"Deny: {result['summary']['deny']}\n",
        f"Warn: {result['summary']['warn']}\n",
        f"Info: {result['summary']['info']}\n",
    ]

    # By-class breakdown
    by_class = result["summary"].get("by_class", {})
    if by_class:
        lines.append("\n## Finding Classes\n\n")
        lines.append("| Class | Count |\n")
        lines.append("|-------|-------|\n")
        for cls, count in sorted(by_class.items()):
            lines.append(f"| `{cls}` | {count} |\n")

    if result["findings"]:
        lines.append("\n## Findings\n\n")
        lines.append("| ID | Severity | Path | Details |\n")
        lines.append("|----|----------|------|---------|\n")
        for f in result["findings"]:
            severity_tag = f["severity"].upper()
            # Escape pipe chars in details for MD table
            details = f["details"].replace("|", "\\|")
            lines.append(
                f"| `{f['id']}` | {severity_tag} "
                f"| `{f['path']}` | {details} |\n"
            )
    else:
        lines.append(
            "\nNo findings — all enforced artifacts pass registry enforcement.\n"
        )

    lines.append(
        f"\n---\n\nGenerated by `run_registry_enforcement.py` "
        f"v{result['version']} at {result['timestamp_utc']}\n"
    )

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
        prog="run_registry_enforcement",
        description=(
            "Registry Enforcement Gate — full Disk / Registry / Evidence / "
            "SoT-Ref reconciliation"
        ),
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
        help=(
            "Strict mode: scan enforced scope directories for "
            "untracked files not in registry"
        ),
    )
    parser.add_argument(
        "--emit-run-ledger", action="store_true",
        help="Write a *_run_ledger.json to output directory",
    )
    args = parser.parse_args()

    # Resolve paths
    repo_root = (
        Path(args.repo_root).resolve() if args.repo_root else _detect_repo_root()
    )
    output_dir = (
        Path(args.output_dir) if args.output_dir else repo_root / REPORT_REL
    )

    if not repo_root.is_dir():
        print(f"ERROR: repo-root not found: {repo_root}", file=sys.stderr)
        return EXIT_ERROR

    # Run enforcement
    try:
        result = run_enforcement(
            repo_root, output_dir,
            strict=args.strict,
            verify_only=args.verify_only,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Print summary
    print(
        f"REGISTRY_ENF: {result['status']} "
        f"(findings: {result['summary']['total_findings']}, "
        f"deny: {result['summary']['deny']}, "
        f"warn: {result['summary']['warn']}, "
        f"info: {result['summary']['info']})"
    )
    for f in result["findings"]:
        severity_tag = f["severity"].upper()
        print(f"  {severity_tag}: {f['id']}: {f['details']}")

    # Write reports (unless --verify-only)
    if args.write_reports and not args.verify_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "registry_enforcement_findings.json"
        md_path = output_dir / "registry_enforcement_report.md"
        json_path.write_text(_findings_to_json(result), encoding="utf-8")
        md_path.write_text(_findings_to_md(result), encoding="utf-8")
        print(f"REPORT: {json_path}")
        print(f"REPORT: {md_path}")

    # Emit run ledger
    if args.emit_run_ledger and not args.verify_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        ledger = _build_run_ledger(result, "registry_enforcement", repo_root)
        ledger_path = output_dir / "registry_enforcement_run_ledger.json"
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
