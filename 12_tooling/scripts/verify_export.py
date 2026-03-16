#!/usr/bin/env python3
"""Deterministic export verification for SSID-open-core export bundles.

Reads an export manifest and optional ZIP bundle, validates:
  - Manifest schema completeness
  - Allow-prefix / deny-glob compliance for every listed file
  - Extension allowlist compliance
  - File-size cap compliance
  - Per-file SHA256 integrity (if ZIP bundle provided)
  - Bundle SHA256 integrity (if ZIP bundle provided)
  - No forbidden paths leaked into the bundle

Exit codes:
  0 = PASS      — all checks passed
  1 = WARN      — soft warnings only (advisory, no hard failures)
  2 = FAIL      — one or more policy breaches
  3 = CORRUPT   — invalid manifest, hash mismatch, or corrupted bundle
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Exit codes (aligned with CC-OC-HARDEN-01 contract)
# ---------------------------------------------------------------------------
EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_CORRUPT = 3

# ---------------------------------------------------------------------------
# Required manifest fields (from export_manifest_schema in policy)
# ---------------------------------------------------------------------------
REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "generated_utc",
    "status",
    "source_repo",
    "source_ref",
    "target_repo",
    "target_ref",
    "policy_file",
    "policy_version",
    "policy_sha256",
    "tool_version",
    "files",
    "excluded_files",
    "bundle_sha256",
}

REQUIRED_FILE_ENTRY_FIELDS = {"path", "sha256", "size_bytes"}
REQUIRED_EXCLUDED_ENTRY_FIELDS = {"path", "reason"}


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_denied(path_posix: str, deny_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_posix, pattern) for pattern in deny_globs)


def is_allowed_prefix(path_posix: str, allow_prefixes: list[str]) -> bool:
    if not allow_prefixes:
        return True
    return any(
        path_posix.startswith(prefix) or path_posix == prefix.rstrip("/")
        for prefix in allow_prefixes
    )


def is_allowed_extension(path_posix: str, allow_extensions: list[str]) -> bool:
    if not allow_extensions:
        return True
    suffix = PurePosixPath(path_posix).suffix.lower()
    if not suffix:
        return True
    return suffix in allow_extensions


class VerificationResult:
    """Collects findings from verification checks."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.corrupt: list[str] = []

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def corruption(self, msg: str) -> None:
        self.corrupt.append(msg)

    @property
    def exit_code(self) -> int:
        if self.corrupt:
            return EXIT_CORRUPT
        if self.failures:
            return EXIT_FAIL
        if self.warnings:
            return EXIT_WARN
        return EXIT_PASS

    def print_report(self) -> None:
        if self.corrupt:
            print("CORRUPT")
            for c in self.corrupt:
                print(f"  CORRUPT: {c}")
        if self.failures:
            print("FAIL")
            for f in self.failures:
                print(f"  FAIL: {f}")
        if self.warnings:
            for w in self.warnings:
                print(f"  WARN: {w}")
        if not self.corrupt and not self.failures and not self.warnings:
            print("PASS")
        elif not self.corrupt and not self.failures:
            print("WARN")


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and return the JSON manifest."""
    text = manifest_path.read_text(encoding="utf-8")
    return json.loads(text)


def load_policy(policy_path: Path) -> dict[str, Any]:
    """Load policy YAML."""
    return yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}


def check_manifest_schema(manifest: dict[str, Any], result: VerificationResult) -> None:
    """Verify all required fields are present in the manifest."""
    missing = REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
    if missing:
        result.fail(f"manifest missing required fields: {sorted(missing)}")

    files = manifest.get("files", [])
    if not isinstance(files, list):
        result.fail("manifest 'files' must be a list")
        return
    for idx, entry in enumerate(files):
        if not isinstance(entry, dict):
            result.fail(f"files[{idx}] is not a dict")
            continue
        entry_missing = REQUIRED_FILE_ENTRY_FIELDS - set(entry.keys())
        if entry_missing:
            result.fail(f"files[{idx}] ({entry.get('path', '?')}) missing fields: {sorted(entry_missing)}")

    excluded = manifest.get("excluded_files", [])
    if not isinstance(excluded, list):
        result.fail("manifest 'excluded_files' must be a list")
        return
    for idx, entry in enumerate(excluded):
        if not isinstance(entry, dict):
            result.fail(f"excluded_files[{idx}] is not a dict")
            continue
        entry_missing = REQUIRED_EXCLUDED_ENTRY_FIELDS - set(entry.keys())
        if entry_missing:
            result.fail(f"excluded_files[{idx}] ({entry.get('path', '?')}) missing fields: {sorted(entry_missing)}")


def check_allowlist_denylist(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    result: VerificationResult,
) -> None:
    """Verify no included file violates allow/deny rules."""
    deny_globs = policy.get("deny_globs", []) or manifest.get("deny_globs", []) or []
    allow_prefixes = policy.get("allow_prefixes", []) or manifest.get("allow_prefixes", []) or []
    allow_extensions = policy.get("allow_extensions", []) or manifest.get("allow_extensions", []) or []
    max_file_size = policy.get("max_file_size_bytes", 0) or manifest.get("max_file_size_bytes", 0) or 0

    files = manifest.get("files", [])
    if not isinstance(files, list):
        return

    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path", "")
        size = entry.get("size_bytes", 0)

        if not is_allowed_prefix(path, allow_prefixes):
            result.fail(f"included file not in allow_prefixes: {path}")

        if is_denied(path, deny_globs):
            result.fail(f"included file matches deny_glob: {path}")

        if not is_allowed_extension(path, allow_extensions):
            result.fail(f"included file has disallowed extension: {path}")

        if max_file_size > 0 and size > max_file_size:
            result.fail(f"included file exceeds max_file_size_bytes ({max_file_size}): {path} ({size} bytes)")


def check_hash_integrity(
    manifest: dict[str, Any],
    zip_path: Path | None,
    result: VerificationResult,
) -> None:
    """Verify SHA256 hashes if a ZIP bundle is provided."""
    if zip_path is None:
        result.warn("no ZIP bundle provided, skipping hash integrity checks")
        return

    if not zip_path.exists():
        result.fail(f"ZIP bundle not found: {zip_path}")
        return

    # Check bundle hash
    expected_bundle_hash = manifest.get("bundle_sha256", "")
    if expected_bundle_hash:
        actual_bundle_hash = sha256_file(zip_path)
        if actual_bundle_hash != expected_bundle_hash:
            result.corruption(
                f"bundle SHA256 mismatch: expected={expected_bundle_hash}, actual={actual_bundle_hash}"
            )
    else:
        result.warn("manifest has no bundle_sha256, cannot verify bundle integrity")

    # Check per-file hashes
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zip_names = set(zf.namelist())
            for entry in files:
                if not isinstance(entry, dict):
                    continue
                path = entry.get("path", "")
                expected_hash = entry.get("sha256", "")
                if not path or not expected_hash:
                    result.corruption(f"file entry missing path or sha256: {entry}")
                    continue

                if path not in zip_names:
                    result.corruption(f"file listed in manifest but missing from ZIP: {path}")
                    continue

                actual_data = zf.read(path)
                actual_hash = sha256_bytes(actual_data)
                if actual_hash != expected_hash:
                    result.corruption(
                        f"file SHA256 mismatch for {path}: expected={expected_hash}, actual={actual_hash}"
                    )

            # Check for files in ZIP not in manifest
            manifest_paths = {e.get("path", "") for e in files if isinstance(e, dict)}
            extra = zip_names - manifest_paths
            if extra:
                result.fail(f"ZIP contains files not in manifest: {sorted(extra)}")

    except zipfile.BadZipFile:
        result.corruption(f"ZIP bundle is corrupted: {zip_path}")


def check_no_forbidden_in_bundle(
    zip_path: Path | None,
    deny_globs: list[str],
    result: VerificationResult,
) -> None:
    """Directly scan ZIP contents for deny-glob matches."""
    if zip_path is None or not zip_path.exists():
        return

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if is_denied(name, deny_globs):
                    result.fail(f"ZIP contains denied path: {name}")
    except zipfile.BadZipFile:
        pass  # already reported in hash check


VALID_PROVENANCE_STATUS = {"unchanged", "redacted", "generated", "excluded"}


def check_sanitization_provenance(
    manifest: dict[str, Any],
    result: VerificationResult,
) -> None:
    """Verify sanitization provenance fields if present."""
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return

    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path", "")
        provenance = entry.get("provenance")
        if provenance is None:
            continue  # provenance is optional for backward compatibility

        if not isinstance(provenance, dict):
            result.fail(f"provenance for {path} must be a dict")
            continue

        status = provenance.get("status")
        if status and status not in VALID_PROVENANCE_STATUS:
            result.fail(
                f"provenance.status for {path} is invalid: {status} "
                f"(must be one of {sorted(VALID_PROVENANCE_STATUS)})"
            )

        public_safe = provenance.get("public_safe")
        if public_safe is not None and not isinstance(public_safe, bool):
            result.fail(f"provenance.public_safe for {path} must be a boolean")

        if entry.get("sanitized") and status != "redacted":
            result.warn(
                f"file {path} is marked sanitized but provenance.status is '{status}', expected 'redacted'"
            )


def verify_export(
    manifest_path: Path,
    policy_path: Path | None = None,
    zip_path: Path | None = None,
) -> VerificationResult:
    """Run all verification checks and return result."""
    result = VerificationResult()

    # Load manifest
    try:
        manifest = load_manifest(manifest_path)
    except (json.JSONDecodeError, OSError) as exc:
        result.corruption(f"cannot load manifest: {exc}")
        return result

    # Check manifest status
    status = manifest.get("status", "")
    if status != "PASS":
        result.fail(f"manifest status is not PASS: {status}")
        return result

    # Load policy (from arg or from manifest reference)
    policy: dict[str, Any] = {}
    if policy_path and policy_path.exists():
        try:
            policy = load_policy(policy_path)
        except Exception as exc:
            result.fail(f"cannot load policy: {exc}")
            return result

    # 1. Schema completeness
    check_manifest_schema(manifest, result)

    # 2. Allowlist / denylist compliance
    check_allowlist_denylist(manifest, policy, result)

    # 3. Hash integrity
    check_hash_integrity(manifest, zip_path, result)

    # 4. Direct ZIP scan for forbidden paths
    deny_globs = policy.get("deny_globs", []) or manifest.get("deny_globs", []) or []
    check_no_forbidden_in_bundle(zip_path, deny_globs, result)

    # 5. Sanitization provenance (if present)
    check_sanitization_provenance(manifest, result)

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_export.py",
        description="Verify an SSID-open-core export bundle against policy.",
    )
    parser.add_argument(
        "manifest",
        help="path to the export manifest JSON",
    )
    parser.add_argument(
        "--policy",
        default=None,
        help="path to the export policy YAML (optional, uses manifest deny_globs if omitted)",
    )
    parser.add_argument(
        "--zip",
        default=None,
        help="path to the export ZIP bundle (optional, enables hash integrity checks)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"FAIL\n  FAIL: manifest not found: {manifest_path}", file=sys.stderr)
        return EXIT_FAIL

    policy_path = Path(args.policy) if args.policy else None
    zip_path = Path(args.zip) if args.zip else None

    result = verify_export(manifest_path, policy_path, zip_path)
    result.print_report()
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
