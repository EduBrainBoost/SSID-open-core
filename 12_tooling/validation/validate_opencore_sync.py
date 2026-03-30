#!/usr/bin/env python3
"""Open-Core Derivation Sync Validator -- read-only export compliance checker.

Compares canonical SSID against derivative SSID-open-core to detect:
- Forbidden artifact leakage (deny-glob violations from opencore_export_policy.yaml)
- Missing expected public derivative artifacts
- Contract hash mismatches between canonical and derivative
- Stale derivative bindings (canonical files newer than derivative copies)
- Registry binding inconsistencies
- Unsanctioned public artifacts (files in derivative not traceable to canonical)
- Export scope violations (files outside allowed export roots)

Usage:
    python validate_opencore_sync.py \
        --canonical-root /path/to/SSID \
        --derivative-root /path/to/SSID-open-core \
        [--contract 16_codex/contracts/sot/sot_contract.yaml] \
        [--export-policy 16_codex/opencore_export_policy.yaml] \
        [--output /path/to/output/dir]

Exit codes:
    0 = PASS (no findings)
    1 = FAIL (forbidden exports, contract mismatch, or critical stale bindings)
    2 = WARN (missing expected exports, registry inconsistencies, etc.)
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML is required. Install via: pip install pyyaml")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FINDING_CLASSES = frozenset(
    {
        "forbidden_export",
        "missing_expected_export",
        "contract_hash_mismatch",
        "stale_derivative_binding",
        "registry_binding_missing",
        "unsanctioned_public_artifact",
        "export_scope_violation",
    }
)

# Default relative paths within the canonical repo.
_DEFAULT_CONTRACT_PATH = "16_codex/contracts/sot/sot_contract.yaml"
_DEFAULT_EXPORT_POLICY_PATH = "16_codex/opencore_export_policy.yaml"
_REGISTRY_PATH = "24_meta_orchestration/registry/sot_registry.json"

# Roots that are expected to appear in the derivative (open-core).
# Derived from the known open-core structure.
_EXPECTED_DERIVATIVE_ROOTS = (
    "03_core",
    "12_tooling",
    "16_codex",
    "23_compliance",
    "24_meta_orchestration",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    """Return hex SHA-256 of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_yaml(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _collect_files(root: Path) -> Set[str]:
    """Collect all files under *root* as POSIX-style relative paths."""
    result: Set[str] = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = Path(dirpath) / fn
            rel = full.relative_to(root).as_posix()
            result.add(rel)
    return result


def _matches_any_glob(path: str, globs: List[str]) -> bool:
    """Check if *path* matches any of the given glob patterns."""
    for pattern in globs:
        if fnmatch.fnmatch(path, pattern):
            return True
        # Also check if the path starts with the pattern prefix
        # (for directory-level globs like "some/dir/**")
        prefix = pattern.replace("/**", "").replace("/*", "")
        if path.startswith(prefix + "/"):
            return True
    return False


def _matches_any_secret_pattern(content: str, patterns: List[str]) -> bool:
    """Check if *content* contains any secret patterns."""
    for pattern in patterns:
        if re.search(pattern, content):
            return True
    return False


# ---------------------------------------------------------------------------
# Export policy loading
# ---------------------------------------------------------------------------


def load_export_policy(policy_path: Path) -> Dict[str, Any]:
    """Load opencore_export_policy.yaml and return structured data."""
    data = _load_yaml(policy_path)
    if not isinstance(data, dict):
        raise ValueError(
            f"Export policy root must be a mapping, got {type(data).__name__}"
        )
    return {
        "version": data.get("version", "unknown"),
        "source_repo": data.get("source_repo", ""),
        "target_repo": data.get("target_repo", ""),
        "mode": data.get("mode", "unknown"),
        "deny_globs": data.get("deny_globs", []),
        "secret_scan_regex": data.get("secret_scan_regex", []),
    }


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def load_registry(repo_root: Path) -> Optional[Dict[str, Any]]:
    """Load sot_registry.json if it exists, else return None."""
    p = repo_root / _REGISTRY_PATH
    if not p.is_file():
        return None
    return _load_json(p)


# ---------------------------------------------------------------------------
# Sync validation
# ---------------------------------------------------------------------------


def _check_forbidden_exports(
    derivative_files: Set[str],
    deny_globs: List[str],
) -> List[Dict[str, Any]]:
    """Check for files in derivative that match deny-globs (forbidden leakage)."""
    findings: List[Dict[str, Any]] = []
    for rel_path in sorted(derivative_files):
        if _matches_any_glob(rel_path, deny_globs):
            findings.append(
                {
                    "class": "forbidden_export",
                    "path": rel_path,
                    "severity": "critical",
                    "detail": (
                        f"Forbidden artifact leaked to derivative: {rel_path} "
                        f"(matches deny-glob)"
                    ),
                }
            )
    return findings


def _check_contract_hash(
    canonical_root: Path,
    derivative_root: Path,
    contract_rel: str,
) -> List[Dict[str, Any]]:
    """Check that the contract hash matches between canonical and derivative."""
    findings: List[Dict[str, Any]] = []
    canonical_contract = canonical_root / contract_rel
    derivative_contract = derivative_root / contract_rel

    if not canonical_contract.is_file():
        # Contract not in canonical -- skip check (handled elsewhere)
        return findings

    if not derivative_contract.is_file():
        # Contract not present in derivative -- not necessarily an error
        # but we record it if contract was expected
        return findings

    canonical_hash = _sha256_file(canonical_contract)
    derivative_hash = _sha256_file(derivative_contract)

    if canonical_hash != derivative_hash:
        findings.append(
            {
                "class": "contract_hash_mismatch",
                "path": contract_rel,
                "severity": "critical",
                "detail": (
                    f"Contract hash mismatch: canonical={canonical_hash[:16]}... "
                    f"derivative={derivative_hash[:16]}..."
                ),
            }
        )
    return findings


def _check_missing_expected_exports(
    canonical_root: Path,
    derivative_root: Path,
    canonical_files: Set[str],
    derivative_files: Set[str],
    deny_globs: List[str],
) -> List[Dict[str, Any]]:
    """Find files expected in derivative (not denied) that are missing."""
    findings: List[Dict[str, Any]] = []

    # Files that are in canonical, within expected derivative roots,
    # not denied, but absent from derivative.
    for rel_path in sorted(canonical_files):
        # Only check files under expected derivative roots
        root = rel_path.split("/")[0] if "/" in rel_path else rel_path
        if root not in _EXPECTED_DERIVATIVE_ROOTS:
            continue

        # Skip denied paths -- they SHOULD be absent
        if _matches_any_glob(rel_path, deny_globs):
            continue

        if rel_path not in derivative_files:
            findings.append(
                {
                    "class": "missing_expected_export",
                    "path": rel_path,
                    "severity": "medium",
                    "detail": (
                        f"Expected public artifact missing from derivative: {rel_path}"
                    ),
                }
            )
    return findings


def _check_stale_bindings(
    canonical_root: Path,
    derivative_root: Path,
    derivative_files: Set[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Check for files where the derivative copy is older than the canonical."""
    findings: List[Dict[str, Any]] = []
    stale_bindings: List[Dict[str, str]] = []

    for rel_path in sorted(derivative_files):
        canonical_file = canonical_root / rel_path
        derivative_file = derivative_root / rel_path

        if not canonical_file.is_file():
            continue  # File only in derivative -- handled by unsanctioned check

        canonical_mtime = canonical_file.stat().st_mtime
        derivative_mtime = derivative_file.stat().st_mtime

        if canonical_mtime > derivative_mtime:
            canonical_ts = datetime.fromtimestamp(
                canonical_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            derivative_ts = datetime.fromtimestamp(
                derivative_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Also check if content actually differs
            if _sha256_file(canonical_file) != _sha256_file(derivative_file):
                findings.append(
                    {
                        "class": "stale_derivative_binding",
                        "path": rel_path,
                        "severity": "high",
                        "detail": (
                            f"Derivative is stale: canonical modified {canonical_ts}, "
                            f"derivative modified {derivative_ts}"
                        ),
                    }
                )
                stale_bindings.append(
                    {
                        "path": rel_path,
                        "canonical_mtime": canonical_ts,
                        "derivative_mtime": derivative_ts,
                    }
                )

    return findings, stale_bindings


def _check_unsanctioned_artifacts(
    canonical_files: Set[str],
    derivative_files: Set[str],
) -> List[Dict[str, Any]]:
    """Find files in derivative that have no canonical counterpart."""
    findings: List[Dict[str, Any]] = []
    # Well-known derivative-only files that are expected
    derivative_only_allowed = {
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "pytest.ini",
        ".gitignore",
        ".github/workflows/ci.yml",
    }

    for rel_path in sorted(derivative_files):
        if rel_path in canonical_files:
            continue
        if rel_path in derivative_only_allowed:
            continue
        # Skip hidden/meta files
        if rel_path.startswith("."):
            continue

        findings.append(
            {
                "class": "unsanctioned_public_artifact",
                "path": rel_path,
                "severity": "medium",
                "detail": (
                    f"Derivative contains artifact with no canonical source: {rel_path}"
                ),
            }
        )
    return findings


def _check_export_scope(
    derivative_files: Set[str],
) -> List[Dict[str, Any]]:
    """Check that derivative files are within allowed export roots."""
    findings: List[Dict[str, Any]] = []
    # Derivative-only top-level files are allowed
    derivative_only_allowed_prefixes = {
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "pytest.ini",
        ".gitignore",
        ".github",
        "docs",
    }

    for rel_path in sorted(derivative_files):
        root = rel_path.split("/")[0] if "/" in rel_path else rel_path
        if root in _EXPECTED_DERIVATIVE_ROOTS:
            continue
        if root in derivative_only_allowed_prefixes:
            continue
        if rel_path.startswith("."):
            continue

        findings.append(
            {
                "class": "export_scope_violation",
                "path": rel_path,
                "severity": "high",
                "detail": (
                    f"File in derivative outside allowed export roots: {rel_path}"
                ),
            }
        )
    return findings


def _check_registry_bindings(
    canonical_root: Path,
    derivative_root: Path,
    canonical_registry: Optional[Dict[str, Any]],
    derivative_registry: Optional[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], str]:
    """Check registry binding consistency between canonical and derivative."""
    findings: List[Dict[str, Any]] = []

    if canonical_registry is None:
        return findings, "unknown"

    if derivative_registry is None:
        findings.append(
            {
                "class": "registry_binding_missing",
                "path": _REGISTRY_PATH,
                "severity": "medium",
                "detail": "Derivative repo is missing sot_registry.json",
            }
        )
        return findings, "inconsistent"

    # Compare schema versions
    canonical_version = canonical_registry.get("schema_version", "unknown")
    derivative_version = derivative_registry.get("schema_version", "unknown")

    if canonical_version != derivative_version:
        findings.append(
            {
                "class": "registry_binding_missing",
                "path": _REGISTRY_PATH,
                "severity": "medium",
                "detail": (
                    f"Registry schema version mismatch: "
                    f"canonical={canonical_version}, derivative={derivative_version}"
                ),
            }
        )
        return findings, "inconsistent"

    # Check that shared artifacts have matching hashes
    canonical_artifacts = {
        a["path"]: a
        for a in canonical_registry.get("roots", {}).get("sot_artifacts", [])
        if "path" in a
    }
    derivative_artifacts = {
        a["path"]: a
        for a in derivative_registry.get("roots", {}).get("sot_artifacts", [])
        if "path" in a
    }

    inconsistent = False
    for path, d_art in derivative_artifacts.items():
        c_art = canonical_artifacts.get(path)
        if c_art is None:
            continue  # Derivative may have subset
        c_hash = c_art.get("hash_sha256", "")
        d_hash = d_art.get("hash_sha256", "")
        if c_hash and d_hash and c_hash != d_hash:
            findings.append(
                {
                    "class": "registry_binding_missing",
                    "path": path,
                    "severity": "medium",
                    "detail": (
                        f"Registry hash mismatch for {path}: "
                        f"canonical={c_hash[:16]}... derivative={d_hash[:16]}..."
                    ),
                }
            )
            inconsistent = True

    status = "inconsistent" if inconsistent else "consistent"
    return findings, status


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------


def scan(
    canonical_root: str,
    derivative_root: str,
    contract_rel: Optional[str] = None,
    export_policy_rel: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the open-core sync validation and return the result dict.

    Parameters
    ----------
    canonical_root:
        Root of the canonical SSID repository.
    derivative_root:
        Root of the derivative SSID-open-core repository.
    contract_rel:
        Relative path to sot_contract.yaml within canonical repo.
    export_policy_rel:
        Relative path to opencore_export_policy.yaml within canonical repo.

    Returns
    -------
    dict with all mandatory output fields conforming to
    export_sync_manifest_schema.json.
    """
    c_root = Path(canonical_root).resolve()
    d_root = Path(derivative_root).resolve()

    if contract_rel is None:
        contract_rel = _DEFAULT_CONTRACT_PATH
    if export_policy_rel is None:
        export_policy_rel = _DEFAULT_EXPORT_POLICY_PATH

    # Load export policy
    policy_path = c_root / export_policy_rel
    if not policy_path.is_file():
        raise FileNotFoundError(f"Export policy not found: {policy_path}")
    policy = load_export_policy(policy_path)
    deny_globs = policy["deny_globs"]
    # secret_patterns = policy["secret_scan_regex"]  # reserved for future use

    # Contract info
    contract_path = c_root / contract_rel
    contract_version = "unknown"
    contract_sha256 = ""
    if contract_path.is_file():
        contract_data = _load_yaml(contract_path)
        contract_version = (
            contract_data.get("version", "unknown")
            if isinstance(contract_data, dict)
            else "unknown"
        )
        contract_sha256 = _sha256_file(contract_path)

    # Collect all files
    canonical_files = _collect_files(c_root)
    derivative_files = _collect_files(d_root)

    # Run all checks
    all_findings: List[Dict[str, Any]] = []

    # 1. Forbidden exports (deny-glob leakage)
    all_findings.extend(
        _check_forbidden_exports(derivative_files, deny_globs)
    )

    # 2. Contract hash mismatch
    all_findings.extend(
        _check_contract_hash(c_root, d_root, contract_rel)
    )

    # 3. Missing expected exports
    all_findings.extend(
        _check_missing_expected_exports(
            c_root, d_root, canonical_files, derivative_files, deny_globs
        )
    )

    # 4. Stale derivative bindings
    stale_findings, stale_bindings = _check_stale_bindings(
        c_root, d_root, derivative_files
    )
    all_findings.extend(stale_findings)

    # 5. Unsanctioned public artifacts
    all_findings.extend(
        _check_unsanctioned_artifacts(canonical_files, derivative_files)
    )

    # 6. Export scope violations
    all_findings.extend(
        _check_export_scope(derivative_files)
    )

    # 7. Registry binding consistency
    canonical_registry = load_registry(c_root)
    derivative_registry = load_registry(d_root)
    registry_findings, registry_status = _check_registry_bindings(
        c_root, d_root, canonical_registry, derivative_registry
    )
    all_findings.extend(registry_findings)

    # Compute allowed/actual/missing/forbidden export lists
    allowed_exports = sorted(
        p
        for p in canonical_files
        if p.split("/")[0] in _EXPECTED_DERIVATIVE_ROOTS
        and not _matches_any_glob(p, deny_globs)
    )
    actual_exports = sorted(derivative_files)
    missing_exports = sorted(
        p for p in allowed_exports if p not in derivative_files
    )
    forbidden_exports = sorted(
        p for p in derivative_files if _matches_any_glob(p, deny_globs)
    )

    # Determine overall status
    has_critical = any(f["severity"] == "critical" for f in all_findings)
    has_fail_class = any(
        f["class"] in ("forbidden_export", "contract_hash_mismatch")
        for f in all_findings
    )
    has_findings = len(all_findings) > 0

    if has_critical or has_fail_class:
        status = "fail"
    elif has_findings:
        status = "warn"
    else:
        status = "pass"

    # Build evidence hash
    manifest_data = json.dumps(
        {
            "scan_time_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "findings_count": len(all_findings),
            "status": status,
        },
        sort_keys=True,
    )
    evidence_sha256 = hashlib.sha256(manifest_data.encode("utf-8")).hexdigest()

    return {
        "scan_time_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "canonical_repo": c_root.name,
        "derivative_repo": d_root.name,
        "contract_path": contract_rel,
        "contract_version": contract_version,
        "contract_sha256": contract_sha256,
        "derivation_mode": policy.get("mode", "public_subset"),
        "allowed_exports": allowed_exports,
        "actual_exports": actual_exports,
        "missing_exports": missing_exports,
        "forbidden_exports": forbidden_exports,
        "stale_bindings": stale_bindings,
        "registry_binding_status": registry_status,
        "findings": all_findings,
        "status": status,
        "evidence_sha256": evidence_sha256,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Open-Core Derivation Sync Validator -- "
            "read-only export compliance checker"
        ),
    )
    parser.add_argument(
        "--canonical-root",
        required=True,
        help="Root of the canonical SSID repository",
    )
    parser.add_argument(
        "--derivative-root",
        required=True,
        help="Root of the derivative SSID-open-core repository",
    )
    parser.add_argument(
        "--contract",
        default=None,
        help=(
            "Relative path to sot_contract.yaml within canonical repo "
            f"(default: {_DEFAULT_CONTRACT_PATH})"
        ),
    )
    parser.add_argument(
        "--export-policy",
        default=None,
        help=(
            "Relative path to opencore_export_policy.yaml within canonical repo "
            f"(default: {_DEFAULT_EXPORT_POLICY_PATH})"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output directory for manifest JSON (default: stdout)",
    )
    args = parser.parse_args(argv)

    result = scan(
        canonical_root=args.canonical_root,
        derivative_root=args.derivative_root,
        contract_rel=args.contract,
        export_policy_rel=args.export_policy,
    )

    output_json = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)

    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "export_sync_manifest.json"
        out_path.write_text(output_json + "\n", encoding="utf-8")
        print(f"Manifest written to {out_path}", file=sys.stderr)
    else:
        print(output_json)

    if result["status"] == "fail":
        sys.exit(1)
    elif result["status"] == "warn":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
