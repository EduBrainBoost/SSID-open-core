#!/usr/bin/env python3
"""
Promotion Gate — cross-repo validation of SSID (canonical) vs SSID-open-core (derivative).

Validates that the derivative repo only contains approved, unmodified, non-sensitive
artifacts from the canonical repo within allowed export scopes.

Produces: promotion_findings.json, promotion_report.md
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
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

# ---------------------------------------------------------------------------
# Export Allow-List — Phase-1 scopes (relative to repo root)
# ---------------------------------------------------------------------------
EXPORT_ALLOW_SCOPES: list[str] = [
    "03_core/",
    "12_tooling/",
    "16_codex/",
    "23_compliance/",
    "24_meta_orchestration/",
    "docs/",
    ".github/workflows/",
]

# ---------------------------------------------------------------------------
# Forbidden patterns — MUST NOT appear in derivative
# ---------------------------------------------------------------------------
FORBIDDEN_GLOB_PATTERNS: list[str] = [
    ".env*",
    "**/.env*",
    "**/secrets/*",
    "secrets/*",
    "**/quarantine/*",
    "**/*.lock",
    "*.lock",
    "**/internal-only/**",
    "internal-only/**",
    "02_audit_logging/quarantine/**",
    "locks/**",
    ".claude/**",
]

# Sensitive content patterns (for unsanitized_artifact check)
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"password\s*[=:]", re.IGNORECASE),
    re.compile(r"secret\s*[=:]", re.IGNORECASE),
    re.compile(r"token\s*[=:]", re.IGNORECASE),
    re.compile(r"api_key\s*[=:]", re.IGNORECASE),
    re.compile(r"private_key\s*[=:]", re.IGNORECASE),
]

# File extensions to scan for sensitive content
_SCANNABLE_EXTENSIONS: set[str] = {
    ".py", ".json", ".yaml", ".yml", ".md", ".txt", ".log",
    ".cfg", ".ini", ".toml", ".env", ".sh", ".ps1", ".rego",
}

REGISTRY_REL = "24_meta_orchestration/registry/sot_registry.json"

# Exit codes
EXIT_PASS = 0
EXIT_WARN = 1
EXIT_DENY = 2
EXIT_ERROR = 3


# ---------------------------------------------------------------------------
# Normalization (inlined — cross-repo import not possible)
# ---------------------------------------------------------------------------

def _normalize_hash(raw: str) -> str:
    """Strip 'sha256:' prefix if present, return lowercase hex."""
    if raw.startswith("sha256:"):
        return raw[7:].lower().strip()
    return raw.lower().strip()


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
    """Generate finding ID: PROMO-{class}-{hash8}."""
    h8 = _sha256_string(path)[:8]
    return f"PROMO-{finding_class}-{h8}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_files(root: Path) -> list[str]:
    """Collect all files under root as POSIX-style relative paths.

    Skips .git directory.
    """
    results: list[str] = []
    if not root.is_dir():
        return results
    for fpath in root.rglob("*"):
        if not fpath.is_file():
            continue
        rel = fpath.relative_to(root).as_posix()
        # Skip .git internals
        if rel.startswith(".git/") or rel == ".git":
            continue
        results.append(rel)
    return sorted(results)


def _is_in_export_scope(path: str) -> bool:
    """Check if path falls within Phase-1 export-allowed scopes."""
    for scope in EXPORT_ALLOW_SCOPES:
        if path.startswith(scope):
            return True
    return False


def _matches_forbidden_pattern(path: str) -> str | None:
    """Check if path matches any forbidden pattern. Returns matched pattern or None."""
    for pattern in FORBIDDEN_GLOB_PATTERNS:
        if fnmatch(path, pattern):
            return pattern
        # Also check with forward-slash-based matching for deeper patterns
        parts = path.split("/")
        for i in range(len(parts)):
            subpath = "/".join(parts[i:])
            if fnmatch(subpath, pattern):
                return pattern
    return None


def _scan_sensitive_content(filepath: Path) -> list[tuple[int, str]]:
    """Scan file for sensitive content patterns.

    Returns list of (line_number, matched_pattern_name).
    """
    if filepath.suffix.lower() not in _SCANNABLE_EXTENSIONS:
        return []
    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        for pattern in _SENSITIVE_PATTERNS:
            if pattern.search(line):
                hits.append((i, pattern.pattern.split(r"\s")[0].lower()))
                break  # one hit per line is enough
    return hits


# ---------------------------------------------------------------------------
# Core promotion logic
# ---------------------------------------------------------------------------

def run_promotion_gate(
    canonical_root: Path,
    derivative_root: Path,
    output_dir: Path,
    strict: bool = False,
) -> Dict[str, Any]:
    """Run cross-repo promotion gate. Returns structured result.

    Args:
        canonical_root: Path to SSID (canonical/source) repo root.
        derivative_root: Path to SSID-open-core (derivative) repo root.
        output_dir: Directory for report outputs.
        strict: If True, every finding is treated as deny-level.

    Returns:
        dict with gate, status, summary, findings.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    findings: List[Dict[str, Any]] = []

    # --- Pre-flight: verify both repos exist ---
    if not canonical_root.is_dir():
        findings.append({
            "id": _finding_id("repo_missing", str(canonical_root)),
            "class": "repo_missing",
            "severity": "deny",
            "source": "promotion_gate",
            "path": str(canonical_root),
            "details": f"Canonical repo not found: {canonical_root}",
            "timestamp_utc": ts,
            "canonical_repo": str(canonical_root),
            "derivative_repo": str(derivative_root),
        })
        return _build_result(ts, canonical_root, derivative_root, findings)

    if not derivative_root.is_dir():
        findings.append({
            "id": _finding_id("repo_missing", str(derivative_root)),
            "class": "repo_missing",
            "severity": "deny",
            "source": "promotion_gate",
            "path": str(derivative_root),
            "details": f"Derivative repo not found: {derivative_root}",
            "timestamp_utc": ts,
            "canonical_repo": str(canonical_root),
            "derivative_repo": str(derivative_root),
        })
        return _build_result(ts, canonical_root, derivative_root, findings)

    # Collect file inventories
    canonical_files: set[str] = set(_collect_files(canonical_root))
    derivative_files: set[str] = set(_collect_files(derivative_root))

    # Load canonical registry (if available) for registry-link checks
    canonical_registry: Dict[str, Any] | None = None
    registry_paths: set[str] = set()
    registry_path = canonical_root / REGISTRY_REL
    if registry_path.is_file():
        try:
            canonical_registry = json.loads(
                registry_path.read_text(encoding="utf-8")
            )
            for art in canonical_registry.get("roots", {}).get("sot_artifacts", []):
                registry_paths.add(art.get("path", ""))
        except (json.JSONDecodeError, OSError):
            canonical_registry = None

    # -----------------------------------------------------------------------
    # Rule 8: export_scope_violation
    # Files in derivative that are outside allowed export scopes
    # -----------------------------------------------------------------------
    for dpath in sorted(derivative_files):
        if not _is_in_export_scope(dpath):
            # Exclude common root-level files that are expected in any repo
            root_level_allow = {
                "README.md", "LICENSE", "CONTRIBUTING.md",
                "pytest.ini", "setup.py", "setup.cfg",
                "pyproject.toml", "requirements.txt",
                ".gitignore", ".gitattributes",
            }
            if dpath in root_level_allow:
                continue
            findings.append({
                "id": _finding_id("export_scope_violation", dpath),
                "class": "export_scope_violation",
                "severity": "deny",
                "source": "promotion_gate",
                "path": dpath,
                "details": (
                    f"Derivative file '{dpath}' is outside allowed "
                    f"export scopes: {EXPORT_ALLOW_SCOPES}"
                ),
                "timestamp_utc": ts,
                "canonical_repo": str(canonical_root),
                "derivative_repo": str(derivative_root),
            })

    # -----------------------------------------------------------------------
    # Rule 3: forbidden_public_artifact
    # Files in derivative matching forbidden patterns
    # -----------------------------------------------------------------------
    for dpath in sorted(derivative_files):
        matched_pattern = _matches_forbidden_pattern(dpath)
        if matched_pattern:
            findings.append({
                "id": _finding_id("forbidden_public_artifact", dpath),
                "class": "forbidden_public_artifact",
                "severity": "deny",
                "source": "promotion_gate",
                "path": dpath,
                "details": (
                    f"Forbidden artifact in derivative: '{dpath}' "
                    f"matches pattern '{matched_pattern}'"
                ),
                "timestamp_utc": ts,
                "canonical_repo": str(canonical_root),
                "derivative_repo": str(derivative_root),
            })

    # -----------------------------------------------------------------------
    # Rule 2: unexpected_derivative_artifact
    # Files in derivative that do NOT exist in canonical and are not root-level
    # -----------------------------------------------------------------------
    for dpath in sorted(derivative_files):
        if dpath not in canonical_files:
            root_level_allow = {
                "README.md", "LICENSE", "CONTRIBUTING.md",
                "pytest.ini", "setup.py", "setup.cfg",
                "pyproject.toml", "requirements.txt",
                ".gitignore", ".gitattributes",
            }
            if dpath in root_level_allow:
                continue
            findings.append({
                "id": _finding_id("unexpected_derivative_artifact", dpath),
                "class": "unexpected_derivative_artifact",
                "severity": "deny",
                "source": "promotion_gate",
                "path": dpath,
                "details": (
                    f"File '{dpath}' exists in derivative but not "
                    f"in canonical repo"
                ),
                "timestamp_utc": ts,
                "canonical_repo": str(canonical_root),
                "derivative_repo": str(derivative_root),
            })

    # -----------------------------------------------------------------------
    # Rule 4: canonical_derivative_hash_drift
    # Same file in both repos but different SHA256
    # -----------------------------------------------------------------------
    common_files = derivative_files & canonical_files
    for cpath in sorted(common_files):
        canonical_hash = _sha256_file(canonical_root / cpath)
        derivative_hash = _sha256_file(derivative_root / cpath)
        if canonical_hash and derivative_hash and canonical_hash != derivative_hash:
            findings.append({
                "id": _finding_id("canonical_derivative_hash_drift", cpath),
                "class": "canonical_derivative_hash_drift",
                "severity": "deny",
                "source": "promotion_gate",
                "path": cpath,
                "details": (
                    f"Hash drift for '{cpath}': "
                    f"canonical={canonical_hash[:16]}... "
                    f"derivative={derivative_hash[:16]}..."
                ),
                "timestamp_utc": ts,
                "canonical_repo": str(canonical_root),
                "derivative_repo": str(derivative_root),
            })

    # -----------------------------------------------------------------------
    # Rule 5: missing_registry_link
    # Derivative artifact not in canonical registry
    # -----------------------------------------------------------------------
    if canonical_registry is not None:
        for dpath in sorted(derivative_files):
            if not _is_in_export_scope(dpath):
                continue
            if dpath not in registry_paths:
                # Only flag files that are in export scope and common
                # Root-level files are exempt
                root_level_allow = {
                    "README.md", "LICENSE", "CONTRIBUTING.md",
                    "pytest.ini", "setup.py", "setup.cfg",
                    "pyproject.toml", "requirements.txt",
                    ".gitignore", ".gitattributes",
                }
                if dpath in root_level_allow:
                    continue
                findings.append({
                    "id": _finding_id("missing_registry_link", dpath),
                    "class": "missing_registry_link",
                    "severity": "deny",
                    "source": "promotion_gate",
                    "path": dpath,
                    "details": (
                        f"Derivative artifact '{dpath}' has no entry "
                        f"in canonical sot_registry.json"
                    ),
                    "timestamp_utc": ts,
                    "canonical_repo": str(canonical_root),
                    "derivative_repo": str(derivative_root),
                })

    # -----------------------------------------------------------------------
    # Rule 6: missing_evidence_link
    # Derivative artifact without evidence_ref in canonical registry
    # -----------------------------------------------------------------------
    if canonical_registry is not None:
        registry_by_path: Dict[str, Dict[str, Any]] = {}
        for art in canonical_registry.get("roots", {}).get("sot_artifacts", []):
            registry_by_path[art.get("path", "")] = art

        for dpath in sorted(derivative_files):
            if dpath in registry_by_path:
                art = registry_by_path[dpath]
                if "evidence_ref" not in art:
                    findings.append({
                        "id": _finding_id("missing_evidence_link", dpath),
                        "class": "missing_evidence_link",
                        "severity": "deny",
                        "source": "promotion_gate",
                        "path": dpath,
                        "details": (
                            f"Artifact '{art.get('name', dpath)}' in derivative "
                            f"has no evidence_ref in canonical registry"
                        ),
                        "timestamp_utc": ts,
                        "canonical_repo": str(canonical_root),
                        "derivative_repo": str(derivative_root),
                    })

                # ---------------------------------------------------------------
                # Rule 7: missing_source_of_truth_ref
                # SoT artifacts without source_of_truth_ref
                # ---------------------------------------------------------------
                sot_ref_prefixes = [
                    "03_core/validators/",
                    "23_compliance/policies/",
                    "24_meta_orchestration/registry/",
                ]
                needs_sot_ref = any(
                    dpath.startswith(p) for p in sot_ref_prefixes
                )
                if needs_sot_ref and "source_of_truth_ref" not in art:
                    findings.append({
                        "id": _finding_id("missing_source_of_truth_ref", dpath),
                        "class": "missing_source_of_truth_ref",
                        "severity": "deny",
                        "source": "promotion_gate",
                        "path": dpath,
                        "details": (
                            f"SoT artifact '{art.get('name', dpath)}' exported "
                            f"to derivative without source_of_truth_ref"
                        ),
                        "timestamp_utc": ts,
                        "canonical_repo": str(canonical_root),
                        "derivative_repo": str(derivative_root),
                    })

    # -----------------------------------------------------------------------
    # Rule 9: unsanitized_artifact
    # Derivative files with sensitive content
    # -----------------------------------------------------------------------
    for dpath in sorted(derivative_files):
        full_path = derivative_root / dpath
        hits = _scan_sensitive_content(full_path)
        if hits:
            hit_summary = "; ".join(
                f"L{ln}: {pname}" for ln, pname in hits[:5]
            )
            findings.append({
                "id": _finding_id("unsanitized_artifact", dpath),
                "class": "unsanitized_artifact",
                "severity": "deny",
                "source": "promotion_gate",
                "path": dpath,
                "details": (
                    f"Sensitive content detected in derivative '{dpath}': "
                    f"{len(hits)} hit(s) — {hit_summary}"
                ),
                "timestamp_utc": ts,
                "canonical_repo": str(canonical_root),
                "derivative_repo": str(derivative_root),
            })

    # -----------------------------------------------------------------------
    # Rule 10: unapproved_derivative_change (WARN only)
    # Derivative has files with different hash that may indicate local changes
    # not reflected back in canonical
    # -----------------------------------------------------------------------
    for cpath in sorted(common_files):
        canonical_hash = _sha256_file(canonical_root / cpath)
        derivative_hash = _sha256_file(derivative_root / cpath)
        if canonical_hash and derivative_hash and canonical_hash != derivative_hash:
            # Already covered by hash_drift as deny; this adds a warn-level note
            findings.append({
                "id": _finding_id("unapproved_derivative_change", cpath),
                "class": "unapproved_derivative_change",
                "severity": "warn",
                "source": "promotion_gate",
                "path": cpath,
                "details": (
                    f"Derivative change in '{cpath}' not reflected in "
                    f"canonical — review required"
                ),
                "timestamp_utc": ts,
                "canonical_repo": str(canonical_root),
                "derivative_repo": str(derivative_root),
            })

    # -----------------------------------------------------------------------
    # Rule 1: missing_required_export_artifact
    # Required artifacts from canonical registry missing in derivative
    # (Phase-1: only check SOT_ALLOWLIST artifacts that are in export scope)
    # -----------------------------------------------------------------------
    if canonical_registry is not None:
        for art in canonical_registry.get("roots", {}).get("sot_artifacts", []):
            art_path = art.get("path", "")
            if not _is_in_export_scope(art_path):
                continue
            if art_path not in derivative_files:
                # Only flag if file exists in canonical
                if (canonical_root / art_path).is_file():
                    findings.append({
                        "id": _finding_id("missing_required_export_artifact", art_path),
                        "class": "missing_required_export_artifact",
                        "severity": "deny",
                        "source": "promotion_gate",
                        "path": art_path,
                        "details": (
                            f"Required export artifact '{art.get('name', art_path)}' "
                            f"missing from derivative repo"
                        ),
                        "timestamp_utc": ts,
                        "canonical_repo": str(canonical_root),
                        "derivative_repo": str(derivative_root),
                    })

    # Apply strict mode: upgrade all warn to deny
    if strict:
        for f in findings:
            if f["severity"] == "warn":
                f["severity"] = "deny"

    return _build_result(ts, canonical_root, derivative_root, findings)


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_result(
    ts: str,
    canonical_root: Path,
    derivative_root: Path,
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

    # Group findings by class for summary
    by_class: Dict[str, int] = {}
    for f in findings:
        cls = f["class"]
        by_class[cls] = by_class.get(cls, 0) + 1

    return {
        "gate": "promotion_gate",
        "version": "1.0.0",
        "timestamp_utc": ts,
        "status": status,
        "canonical_repo": str(canonical_root),
        "derivative_repo": str(derivative_root),
        "summary": {
            "total_findings": len(findings),
            "deny": deny_count,
            "warn": warn_count,
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
        "# Promotion Gate Report\n",
        f"\nTimestamp: {result['timestamp_utc']}\n",
        f"Status: **{result['status']}**\n",
        f"Canonical: `{result['canonical_repo']}`\n",
        f"Derivative: `{result['derivative_repo']}`\n",
        f"Total findings: {result['summary']['total_findings']}\n",
        f"Deny: {result['summary']['deny']}\n",
        f"Warn: {result['summary']['warn']}\n",
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
            details = f["details"].replace("|", "\\|")
            lines.append(
                f"| `{f['id']}` | {severity_tag} "
                f"| `{f['path']}` | {details} |\n"
            )
    else:
        lines.append(
            "\nNo findings — derivative repo passes all promotion checks.\n"
        )

    lines.append(
        f"\n---\n\nGenerated by `run_promotion_gate.py` "
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
        prog="run_promotion_gate",
        description=(
            "Promotion Gate — cross-repo validation of SSID (canonical) "
            "vs SSID-open-core (derivative)"
        ),
    )
    parser.add_argument(
        "--canonical-repo", type=str, required=True,
        help="Path to SSID (canonical/source) repo root",
    )
    parser.add_argument(
        "--derivative-repo", type=str, required=True,
        help="Path to SSID-open-core (derivative) repo root",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Report output directory (default: <canonical-repo>/02_audit_logging/reports)",
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
        help="Strict mode: treat all warnings as deny",
    )
    parser.add_argument(
        "--emit-run-ledger", action="store_true",
        help="Write a *_run_ledger.json to output directory",
    )
    args = parser.parse_args()

    # Resolve paths
    canonical_root = Path(args.canonical_repo).resolve()
    derivative_root = Path(args.derivative_repo).resolve()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else canonical_root / "02_audit_logging" / "reports"
    )

    if not canonical_root.is_dir():
        print(
            f"ERROR: canonical repo not found: {canonical_root}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if not derivative_root.is_dir():
        print(
            f"ERROR: derivative repo not found: {derivative_root}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    # Run promotion gate
    try:
        result = run_promotion_gate(
            canonical_root, derivative_root, output_dir,
            strict=args.strict,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Print summary
    print(
        f"PROMOTION_GATE: {result['status']} "
        f"(findings: {result['summary']['total_findings']}, "
        f"deny: {result['summary']['deny']}, "
        f"warn: {result['summary']['warn']})"
    )
    for f in result["findings"]:
        severity_tag = f["severity"].upper()
        print(f"  {severity_tag}: {f['id']}: {f['details']}")

    # Write reports (unless --verify-only)
    if args.write_reports and not args.verify_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "promotion_findings.json"
        md_path = output_dir / "promotion_report.md"
        json_path.write_text(_findings_to_json(result), encoding="utf-8")
        md_path.write_text(_findings_to_md(result), encoding="utf-8")
        print(f"REPORT: {json_path}")
        print(f"REPORT: {md_path}")

    # Emit run ledger
    if args.emit_run_ledger and not args.verify_only:
        output_dir.mkdir(parents=True, exist_ok=True)
        ledger = _build_run_ledger(
            result, "promotion_gate", canonical_root,
            related_repo=str(derivative_root),
        )
        ledger_path = output_dir / "promotion_gate_run_ledger.json"
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
