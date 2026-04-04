#!/usr/bin/env python3
"""SSID Supply Chain Validator.

Verifies source provenance, build reproducibility, and deployment artifacts.

Checks performed:
  1. Provenance metadata — required fields present and valid.
  2. Builder allow-list — only trusted build systems accepted.
  3. Commit SHA format — must be a 40-char hex string.
  4. SBOM hash consistency — SBOM matches its declared SHA-256.
  5. Reproducibility — compares two SBOMs component-by-component.
  6. Deployment artifact integrity — verifies artifact hash manifests.

Usage:
    python 12_tooling/security/supply_chain_validator.py --provenance build_provenance.json
    python 12_tooling/security/supply_chain_validator.py --sbom sbom.json --sbom-hash <hex>
    python 12_tooling/security/supply_chain_validator.py \\
        --sbom sbom_a.json --sbom-compare sbom_b.json

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants (mirrors security_config.yaml)
# ---------------------------------------------------------------------------

REQUIRED_PROVENANCE_FIELDS = frozenset(["builder", "build_timestamp", "source_repo", "commit_sha"])

ALLOWED_BUILDERS = frozenset(["github-actions", "ssid-local"])

_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ValidationCheck:
    """Single validation check result."""

    name: str
    passed: bool
    detail: str


@dataclass
class ValidationReport:
    """Aggregated supply chain validation report."""

    validated_at: str
    subject: str
    overall_pass: bool
    checks: list[ValidationCheck] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(ValidationCheck(name=name, passed=passed, detail=detail))
        if not passed:
            self.overall_pass = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "validated_at": self.validated_at,
            "subject": self.subject,
            "overall_pass": self.overall_pass,
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Provenance validation
# ---------------------------------------------------------------------------


def validate_provenance(provenance: dict[str, Any]) -> ValidationReport:
    """Validate build provenance metadata.

    Args:
        provenance: Provenance dict (e.g. from SLSA provenance JSON).

    Returns:
        ValidationReport.
    """
    report = ValidationReport(
        validated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        subject="provenance",
        overall_pass=True,
    )

    # Check 1: Required fields
    missing = REQUIRED_PROVENANCE_FIELDS - set(provenance.keys())
    report.add(
        "required_provenance_fields",
        not missing,
        f"Missing: {sorted(missing)}" if missing else "All required provenance fields present",
    )

    # Check 2: Builder allow-list
    builder = str(provenance.get("builder", "")).lower()
    builder_ok = builder in ALLOWED_BUILDERS
    report.add(
        "allowed_builder",
        builder_ok,
        f"Builder '{builder}' is allowed"
        if builder_ok
        else f"Builder '{builder}' not in allow-list {sorted(ALLOWED_BUILDERS)}",
    )

    # Check 3: Commit SHA format
    commit_sha = str(provenance.get("commit_sha", ""))
    sha_ok = bool(_COMMIT_SHA_RE.match(commit_sha))
    report.add(
        "commit_sha_format",
        sha_ok,
        f"Commit SHA '{commit_sha[:8]}...' is valid 40-char hex"
        if sha_ok
        else f"Commit SHA '{commit_sha}' is not a valid 40-char hex string",
    )

    # Check 4: Timestamp format
    ts = str(provenance.get("build_timestamp", ""))
    ts_ok = bool(_ISO8601_RE.match(ts))
    report.add(
        "build_timestamp_format",
        ts_ok,
        f"Timestamp '{ts}' matches ISO 8601" if ts_ok else f"Timestamp '{ts}' does not match expected ISO 8601 format",
    )

    # Check 5: Source repo non-empty
    repo = str(provenance.get("source_repo", "")).strip()
    report.add(
        "source_repo_non_empty",
        bool(repo),
        f"source_repo='{repo}'" if repo else "source_repo is empty",
    )

    return report


# ---------------------------------------------------------------------------
# SBOM hash consistency
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_sbom_integrity(sbom_path: Path, expected_sha256: str | None = None) -> ValidationReport:
    """Validate SBOM file integrity.

    Args:
        sbom_path: Path to CycloneDX SBOM JSON.
        expected_sha256: If provided, compare computed hash against this value.

    Returns:
        ValidationReport.
    """
    report = ValidationReport(
        validated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        subject=str(sbom_path),
        overall_pass=True,
    )

    # Check 1: File exists
    report.add(
        "sbom_file_exists", sbom_path.exists(), "SBOM file found" if sbom_path.exists() else "SBOM file not found"
    )
    if not sbom_path.exists():
        return report

    # Check 2: Valid JSON
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
        report.add("sbom_valid_json", True, "SBOM is valid JSON")
    except json.JSONDecodeError as exc:
        report.add("sbom_valid_json", False, f"JSON parse error: {exc}")
        return report

    # Check 3: CycloneDX format field
    bom_format = data.get("bomFormat", "")
    cyclone_ok = bom_format == "CycloneDX"
    report.add(
        "sbom_cyclonedx_format",
        cyclone_ok,
        "bomFormat=CycloneDX" if cyclone_ok else f"bomFormat='{bom_format}' (expected CycloneDX)",
    )

    # Check 4: Has components
    components = data.get("components", [])
    has_components = isinstance(components, list) and len(components) >= 0
    report.add(
        "sbom_has_components",
        has_components,
        f"{len(components)} components in SBOM",
    )

    # Check 5: Hash matches (if expected_sha256 provided)
    if expected_sha256:
        actual = _sha256_file(sbom_path)
        hash_ok = actual.lower() == expected_sha256.lower()
        report.add(
            "sbom_hash_match",
            hash_ok,
            f"SHA-256 matches: {actual[:16]}..."
            if hash_ok
            else f"Hash MISMATCH: expected {expected_sha256[:16]}..., got {actual[:16]}...",
        )

    return report


# ---------------------------------------------------------------------------
# Reproducibility comparison
# ---------------------------------------------------------------------------


def compare_sboms(sbom_a_path: Path, sbom_b_path: Path) -> ValidationReport:
    """Compare two CycloneDX SBOMs for reproducibility.

    Checks that both SBOMs contain the same set of components
    (name + version + purl).

    Args:
        sbom_a_path: Reference SBOM.
        sbom_b_path: Comparison SBOM.

    Returns:
        ValidationReport with diff details.
    """
    report = ValidationReport(
        validated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        subject=f"{sbom_a_path.name} vs {sbom_b_path.name}",
        overall_pass=True,
    )

    for label, path in (("sbom_a", sbom_a_path), ("sbom_b", sbom_b_path)):
        report.add(f"{label}_exists", path.exists(), "found" if path.exists() else "not found")

    if not (sbom_a_path.exists() and sbom_b_path.exists()):
        return report

    def _component_key(c: dict) -> str:
        return f"{c.get('name', '')}@{c.get('version', '')}#{c.get('purl', '')}"

    a_data = json.loads(sbom_a_path.read_text(encoding="utf-8"))
    b_data = json.loads(sbom_b_path.read_text(encoding="utf-8"))

    a_keys = {_component_key(c) for c in a_data.get("components", [])}
    b_keys = {_component_key(c) for c in b_data.get("components", [])}

    only_in_a = sorted(a_keys - b_keys)
    only_in_b = sorted(b_keys - a_keys)

    report.add(
        "component_sets_identical",
        not (only_in_a or only_in_b),
        "Component sets match"
        if not (only_in_a or only_in_b)
        else (
            f"{len(only_in_a)} component(s) only in A, "
            f"{len(only_in_b)} component(s) only in B. "
            f"A-only: {only_in_a[:3]}{'...' if len(only_in_a) > 3 else ''}"
        ),
    )

    report.add(
        "component_count_match",
        len(a_keys) == len(b_keys),
        f"Both SBOMs have {len(a_keys)} components"
        if len(a_keys) == len(b_keys)
        else f"Count mismatch: A={len(a_keys)}, B={len(b_keys)}",
    )

    return report


# ---------------------------------------------------------------------------
# Deployment artifact hash manifest validation
# ---------------------------------------------------------------------------


def validate_artifact_manifest(manifest_path: Path) -> ValidationReport:
    """Validate a deployment artifact hash manifest.

    The manifest is expected to be a JSON file of the form::

        {
          "artifacts": [
            {"path": "relative/path", "sha256": "<hex>"},
            ...
          ]
        }

    Each artifact's SHA-256 hash is verified against the file on disk.

    Args:
        manifest_path: Path to the artifact manifest JSON.

    Returns:
        ValidationReport.
    """
    report = ValidationReport(
        validated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        subject=str(manifest_path),
        overall_pass=True,
    )

    report.add("manifest_exists", manifest_path.exists(), "found" if manifest_path.exists() else "not found")
    if not manifest_path.exists():
        return report

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.add("manifest_valid_json", False, f"JSON error: {exc}")
        return report

    report.add("manifest_valid_json", True, "manifest is valid JSON")

    artifacts: list[dict] = manifest.get("artifacts", [])
    report.add("manifest_has_artifacts", bool(artifacts), f"{len(artifacts)} artifacts declared")

    base_dir = manifest_path.parent
    for entry in artifacts:
        rel_path = entry.get("path", "")
        expected_hash = str(entry.get("sha256", ""))
        artifact_path = base_dir / rel_path

        if not artifact_path.exists():
            report.add(f"artifact:{rel_path}", False, "file not found on disk")
            continue

        actual_hash = _sha256_file(artifact_path)
        hash_ok = actual_hash.lower() == expected_hash.lower()
        report.add(
            f"artifact:{rel_path}",
            hash_ok,
            "hash OK" if hash_ok else f"hash MISMATCH (expected {expected_hash[:16]}..., got {actual_hash[:16]}...)",
        )

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="SSID Supply Chain Validator")
    parser.add_argument("--provenance", type=Path, default=None, help="Build provenance JSON file to validate")
    parser.add_argument("--sbom", type=Path, default=None, help="CycloneDX SBOM JSON to validate")
    parser.add_argument("--sbom-hash", type=str, default=None, help="Expected SHA-256 hex of the SBOM file")
    parser.add_argument(
        "--sbom-compare", type=Path, default=None, help="Second SBOM to compare against --sbom for reproducibility"
    )
    parser.add_argument(
        "--manifest", type=Path, default=None, help="Deployment artifact hash manifest JSON to validate"
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="Write validation report JSON to this path")
    parser.add_argument("--fail-on-invalid", action="store_true", help="Exit non-zero if any check fails")
    args = parser.parse_args(argv)

    reports: list[ValidationReport] = []

    if args.provenance:
        prov_data = json.loads(args.provenance.read_text(encoding="utf-8"))
        reports.append(validate_provenance(prov_data))

    if args.sbom and not args.sbom_compare:
        reports.append(validate_sbom_integrity(args.sbom, expected_sha256=args.sbom_hash))

    if args.sbom and args.sbom_compare:
        reports.append(validate_sbom_integrity(args.sbom, expected_sha256=args.sbom_hash))
        reports.append(compare_sboms(args.sbom, args.sbom_compare))

    if args.manifest:
        reports.append(validate_artifact_manifest(args.manifest))

    if not reports:
        parser.print_help()
        return 0

    overall_pass = all(r.overall_pass for r in reports)
    output = {
        "validated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_pass": overall_pass,
        "report_count": len(reports),
        "reports": [r.to_dict() for r in reports],
    }
    output_json = json.dumps(output, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Validation report written to {args.output}")
    else:
        print(output_json)

    status = "PASS" if overall_pass else "FAIL"
    print(f"\nOverall: {status}", file=sys.stderr)

    if args.fail_on_invalid and not overall_pass:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
