#!/usr/bin/env python3
"""
Open-Core Export Pipeline — SSID -> SSID-open-core

Reads module.yaml classification per root, applies opencore_export_policy.yaml,
and exports public-safe artefacts with SHA256 hashed manifest.

Exit codes follow verification_exit_codes from policy:
  0 = PASS, 1 = WARN, 2 = FAIL, 3 = CORRUPT
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    # Fallback: minimal YAML loader for simple key-value files
    yaml = None  # type: ignore[assignment]

TOOL_VERSION = "1.0.0"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = "16_codex/opencore_export_policy.yaml"

# Classifications considered "public" — full artifact export
PUBLIC_CLASSIFICATIONS = frozenset(
    {
        "Public Specification",
        "Public Reference",
    }
)

# For non-public modules, only these sub-paths are exportable
RESTRICTED_EXPORT_PATHS = (
    "module.yaml",
    "README.md",
    "docs/",
    "contracts/",
    "interfaces/",
)

# Canonical 24 roots
CANONICAL_ROOTS = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, using PyYAML if available, else minimal parser."""
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return _minimal_yaml_load(text)


def _minimal_yaml_load(text: str) -> dict[str, Any]:
    """Extremely minimal YAML parser — handles flat key: value and lists."""
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item under a key
        if stripped.startswith("- ") and current_key is not None:
            val = stripped[2:].strip().strip('"').strip("'")
            if current_list is not None:
                current_list.append(val)
            continue

        # Key: value
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                result[key] = value
                current_key = None
                current_list = None
            else:
                # Start of a list or nested block — treat as list
                current_key = key
                current_list = []
                result[key] = current_list

    return result


# ---------------------------------------------------------------------------
# Policy loading
# ---------------------------------------------------------------------------


class ExportPolicy:
    """Encapsulates the opencore_export_policy.yaml rules."""

    def __init__(self, policy_path: Path) -> None:
        self.path = policy_path
        raw = _load_yaml(policy_path)
        self.allow_prefixes: list[str] = raw.get("allow_prefixes", [])
        self.allow_extensions: list[str] = raw.get("allow_extensions", [])
        self.max_file_size: int = int(raw.get("max_file_size_bytes", 1_048_576))
        self.deny_globs: list[str] = raw.get("deny_globs", [])
        self.secret_scan_regex: list[re.Pattern[str]] = []
        for pat in raw.get("secret_scan_regex", []):
            try:
                self.secret_scan_regex.append(re.compile(pat))
            except re.error:
                pass  # skip invalid regex gracefully
        self.schema_version: str = raw.get("schema_version", "unknown")
        self.sha256 = sha256_file(policy_path)

    def is_prefix_allowed(self, rel_path: str) -> bool:
        """Check if a relative path starts with any allow prefix."""
        normalized = rel_path.replace("\\", "/")
        return any(normalized.startswith(p) for p in self.allow_prefixes)

    def is_extension_allowed(self, rel_path: str) -> bool:
        """Check if file extension is in the allowed list."""
        suffix = Path(rel_path).suffix.lower()
        if not suffix:
            return False
        return suffix in self.allow_extensions

    def matches_deny_glob(self, rel_path: str) -> str | None:
        """Return the first matching deny glob, or None."""
        normalized = rel_path.replace("\\", "/")
        for glob_pat in self.deny_globs:
            if fnmatch.fnmatch(normalized, glob_pat):
                return glob_pat
        return None

    def scan_secrets(self, content: str) -> list[str]:
        """Return list of matched secret patterns (pattern text only, no PII)."""
        hits: list[str] = []
        for pat in self.secret_scan_regex:
            if pat.search(content):
                hits.append(pat.pattern[:60])
        return hits


# ---------------------------------------------------------------------------
# Module classification
# ---------------------------------------------------------------------------


def load_module_classification(root_dir: Path) -> str:
    """Read classification from module.yaml. Returns 'Unknown' on failure."""
    mod_yaml = root_dir / "module.yaml"
    if not mod_yaml.is_file():
        return "Unknown"
    try:
        data = _load_yaml(mod_yaml)
        return str(data.get("classification", "Unknown"))
    except Exception:
        return "Unknown"


def is_public_module(classification: str) -> bool:
    """Check if classification is public."""
    return classification in PUBLIC_CLASSIFICATIONS


# ---------------------------------------------------------------------------
# SHA256 utilities
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------


def collect_source_files(source_root: Path) -> list[Path]:
    """Collect all files under source_root (excluding .git)."""
    files: list[Path] = []
    for p in source_root.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            files.append(p)
    return sorted(files)


def is_restricted_exportable(rel_path: str) -> bool:
    """For non-public modules, check if the file is in the restricted export set."""
    normalized = rel_path.replace("\\", "/")
    parts = normalized.split("/", 1)
    if len(parts) < 2:
        return False
    inner = parts[1]
    for allowed in RESTRICTED_EXPORT_PATHS:
        if allowed.endswith("/"):
            if inner.startswith(allowed) or inner == allowed.rstrip("/"):
                return True
        else:
            if inner == allowed:
                return True
    return False


# ---------------------------------------------------------------------------
# Export engine
# ---------------------------------------------------------------------------


class ExportResult:
    """Holds the result of an export run."""

    def __init__(self) -> None:
        self.exported: list[dict[str, Any]] = []
        self.excluded: list[dict[str, str]] = []
        self.warnings: list[str] = []
        self.module_classifications: dict[str, str] = {}

    @property
    def status(self) -> str:
        if any(e.get("reason") == "secret_detected" for e in self.excluded):
            return "FAIL"
        return "PASS"


def run_export(
    source_repo: Path,
    target_repo: Path,
    policy: ExportPolicy,
    *,
    dry_run: bool = False,
    source_ref: str = "HEAD",
) -> ExportResult:
    """Execute the open-core export pipeline.

    Args:
        source_repo: Path to SSID repo root.
        target_repo: Path to SSID-open-core repo root.
        policy: Loaded ExportPolicy.
        dry_run: If True, do not write files, only compute manifest.
        source_ref: Git ref or SHA of source (for manifest metadata).

    Returns:
        ExportResult with exported/excluded file lists.
    """
    result = ExportResult()

    # 1. Load module classifications
    for root_name in CANONICAL_ROOTS:
        root_dir = source_repo / root_name
        if root_dir.is_dir():
            classification = load_module_classification(root_dir)
            result.module_classifications[root_name] = classification

    # 2. Collect all candidate files
    all_files = collect_source_files(source_repo)

    for fpath in all_files:
        rel = fpath.relative_to(source_repo).as_posix()

        # 2a. Check allow_prefixes
        if not policy.is_prefix_allowed(rel):
            result.excluded.append({"path": rel, "reason": "not_in_allow_prefix"})
            continue

        # 2b. Check extension
        if not policy.is_extension_allowed(rel):
            result.excluded.append({"path": rel, "reason": "extension_denied"})
            continue

        # 2c. Check deny globs
        deny_match = policy.matches_deny_glob(rel)
        if deny_match is not None:
            result.excluded.append({"path": rel, "reason": f"deny_glob:{deny_match}"})
            continue

        # 2d. Check file size
        try:
            file_size = fpath.stat().st_size
        except OSError:
            result.excluded.append({"path": rel, "reason": "stat_error"})
            continue

        if file_size > policy.max_file_size:
            result.excluded.append({"path": rel, "reason": "oversized"})
            continue

        # 2e. Module-level classification filter
        root_name = rel.split("/")[0]
        if root_name in result.module_classifications:
            classification = result.module_classifications[root_name]
            if not is_public_module(classification):
                if not is_restricted_exportable(rel):
                    result.excluded.append(
                        {
                            "path": rel,
                            "reason": f"internal_module:{classification}",
                        }
                    )
                    continue

        # 2f. Secret scan
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            result.excluded.append({"path": rel, "reason": "read_error"})
            continue

        secret_hits = policy.scan_secrets(content)
        if secret_hits:
            result.excluded.append({"path": rel, "reason": "secret_detected"})
            result.warnings.append(f"SECRET_DETECTED in {rel} — matched {len(secret_hits)} pattern(s)")
            continue

        # 2g. File passes all gates -> export
        file_hash = sha256_file(fpath)
        entry = {
            "path": rel,
            "sha256": file_hash,
            "size_bytes": file_size,
        }
        result.exported.append(entry)

        # 2h. Copy to target
        if not dry_run:
            target_path = target_repo / rel
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(fpath), str(target_path))

    return result


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


def generate_manifest(
    result: ExportResult,
    policy: ExportPolicy,
    *,
    source_ref: str = "HEAD",
    target_ref: str = "HEAD",
) -> dict[str, Any]:
    """Generate the export manifest conforming to export_manifest_schema."""
    now_utc = datetime.now(UTC).isoformat()

    # Compute bundle hash over all exported file hashes (deterministic)
    bundle_data = "".join(e["sha256"] for e in sorted(result.exported, key=lambda x: x["path"]))
    bundle_sha256 = sha256_bytes(bundle_data.encode("utf-8"))

    manifest: dict[str, Any] = {
        "schema_version": policy.schema_version,
        "generated_utc": now_utc,
        "status": result.status,
        "source_repo": "SSID",
        "source_ref": source_ref,
        "target_repo": "SSID-open-core",
        "target_ref": target_ref,
        "policy_file": str(policy.path.name),
        "policy_version": policy.schema_version,
        "policy_sha256": policy.sha256,
        "tool_version": TOOL_VERSION,
        "module_classifications": result.module_classifications,
        "files": result.exported,
        "excluded_files": result.excluded,
        "bundle_sha256": bundle_sha256,
    }
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_source_ref(repo: Path) -> str:
    """Try to get current git SHA; fall back to 'unknown'."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SSID Open-Core Export Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO_ROOT,
        help="Source SSID repo root (default: auto-detected)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Target SSID-open-core repo root",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Path to opencore_export_policy.yaml (default: <source>/16_codex/opencore_export_policy.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute manifest without writing files",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Write export manifest JSON to this path (default: stdout)",
    )
    parser.add_argument(
        "--source-ref",
        default=None,
        help="Git ref/SHA of source (default: auto-detect HEAD)",
    )

    args = parser.parse_args(argv)

    # Resolve policy path
    policy_path = args.policy
    if policy_path is None:
        policy_path = args.source / DEFAULT_POLICY_PATH
        if not policy_path.is_file():
            # Also check target repo for the policy
            alt = args.target / DEFAULT_POLICY_PATH
            if alt.is_file():
                policy_path = alt

    if not policy_path.is_file():
        print(f"FAIL: Policy file not found: {policy_path}", file=sys.stderr)
        return 2

    # Load policy
    policy = ExportPolicy(policy_path)

    # Resolve source ref
    source_ref = args.source_ref or _resolve_source_ref(args.source)

    # Validate paths
    if not args.source.is_dir():
        print(f"FAIL: Source repo not found: {args.source}", file=sys.stderr)
        return 2

    if not args.dry_run and not args.target.is_dir():
        print(f"FAIL: Target repo not found: {args.target}", file=sys.stderr)
        return 2

    # Run export
    result = run_export(
        args.source,
        args.target,
        policy,
        dry_run=args.dry_run,
        source_ref=source_ref,
    )

    # Generate manifest
    manifest = generate_manifest(
        result,
        policy,
        source_ref=source_ref,
    )

    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False)

    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(manifest_json, encoding="utf-8")
        print(f"Manifest written to: {args.manifest_out}")
    else:
        print(manifest_json)

    # Summary
    n_exported = len(result.exported)
    n_excluded = len(result.excluded)
    mode = "DRY-RUN" if args.dry_run else "EXPORT"
    print(
        f"\n[{mode}] {result.status} — {n_exported} files exported, {n_excluded} excluded",
        file=sys.stderr,
    )

    if result.warnings:
        for w in result.warnings:
            print(f"  WARNING: {w}", file=sys.stderr)
        return 2  # secret detected = FAIL

    return 0 if result.status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
