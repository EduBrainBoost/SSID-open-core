#!/usr/bin/env python3
"""OpenCore Drift Sentinel -- compares SSID main against SSID-open-core main.

Checks that every file in the open-core mirror:
  1. Is present in the SSID source at the same relative path
  2. Has identical content (byte-for-byte)
  3. Conforms to the allowlist / denylist policy

Exit codes:
  0 -- clean (no drift)
  2 -- drift detected
  3 -- error (config, git, or policy problem)

Outputs a JSON report to stdout (or --output-file).
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_POLICY = "16_codex/opencore_export_policy.yaml"
DEFAULT_ALLOWLIST = "23_compliance/policies/open_core_export_allowlist.yaml"

EXIT_CLEAN = 0
EXIT_DRIFT = 2
EXIT_ERROR = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, args: list[str], text: bool = True) -> str | bytes:
    cmd = ["git", "-C", str(repo), *args]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=text)
    if proc.returncode != 0:
        stderr = proc.stderr if text else proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{stderr.strip()}")
    return proc.stdout if text else proc.stdout


def git_ls_tree(repo: Path, ref: str) -> list[str]:
    raw = str(git(repo, ["ls-tree", "-r", "--name-only", ref]))
    return [p.strip() for p in raw.splitlines() if p.strip()]


def git_file_hash(repo: Path, ref: str, path: str) -> str:
    """Return SHA-256 of a file's content at a given ref."""
    blob = git(repo, ["show", f"{ref}:{path}"], text=False)
    blob_bytes = blob if isinstance(blob, bytes) else blob.encode("utf-8")
    return sha256_bytes(blob_bytes)


def git_head_sha(repo: Path) -> str:
    return str(git(repo, ["rev-parse", "HEAD"])).strip()


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------
def load_yaml_safe(path: Path) -> dict[str, Any]:
    """Load YAML without requiring pyyaml -- falls back to a simple parser."""
    try:
        import yaml  # noqa: F811

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        # Minimal fallback for list-of-strings YAML
        data: dict[str, Any] = {}
        current_key: str | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- "):
                if current_key:
                    data.setdefault(current_key, []).append(stripped[2:].strip().strip("\"'"))
            elif ":" in stripped:
                key = stripped.split(":")[0].strip()
                val = stripped.split(":", 1)[1].strip()
                current_key = key
                if val and not val.startswith("|") and not val.startswith(">"):
                    data[key] = val.strip("\"'")
        return data


def is_denied_by_glob(path_posix: str, deny_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_posix, g) for g in deny_globs)


def is_in_deny_roots(path_posix: str, deny_roots: list[str]) -> bool:
    for root in deny_roots:
        root_prefix = root.rstrip("/") + "/"
        if path_posix.startswith(root_prefix) or path_posix == root.rstrip("/"):
            return True
    return False


def is_in_allow_prefixes(path_posix: str, allow_prefixes: list[str]) -> bool:
    for prefix in allow_prefixes:
        if prefix.endswith("/"):
            if path_posix.startswith(prefix):
                return True
        else:
            if path_posix == prefix:
                return True
    return False


# ---------------------------------------------------------------------------
# Core drift detection
# ---------------------------------------------------------------------------
def detect_drift(
    ssid_repo: Path,
    opencore_repo: Path,
    policy_path: Path,
    allowlist_path: Path | None,
    ssid_ref: str = "HEAD",
    opencore_ref: str = "HEAD",
) -> dict[str, Any]:
    """Compare SSID against SSID-open-core and return drift report."""
    policy = load_yaml_safe(policy_path)
    deny_globs = policy.get("deny_globs", []) or []
    deny_roots = policy.get("deny_roots", []) or []
    allow_prefixes = policy.get("allow_prefixes", []) or []

    if allowlist_path and allowlist_path.exists():
        load_yaml_safe(allowlist_path)

    ssid_sha = git_head_sha(ssid_repo) if ssid_ref == "HEAD" else ssid_ref
    oc_sha = git_head_sha(opencore_repo) if opencore_ref == "HEAD" else opencore_ref

    ssid_files = set(git_ls_tree(ssid_repo, ssid_ref))
    oc_files = set(git_ls_tree(opencore_repo, opencore_ref))

    drift_items: list[dict[str, str]] = []
    policy_violations: list[dict[str, str]] = []

    # 1. Files in open-core that should not be there (deny policy)
    for f in sorted(oc_files):
        if is_denied_by_glob(f, deny_globs):
            policy_violations.append(
                {
                    "file": f,
                    "violation": "matches_deny_glob",
                    "detail": "File matches a deny_globs pattern in export policy",
                }
            )
        if is_in_deny_roots(f, deny_roots):
            policy_violations.append(
                {
                    "file": f,
                    "violation": "in_deny_root",
                    "detail": "File is under a denied root directory",
                }
            )

    # 2. Files in open-core but NOT in SSID source
    orphaned = sorted(oc_files - ssid_files)
    for f in orphaned:
        drift_items.append(
            {
                "file": f,
                "type": "orphaned_in_opencore",
                "detail": "Present in open-core but not in SSID source",
            }
        )

    # 3. Content drift -- files in both repos but different content
    common = sorted(oc_files & ssid_files)
    for f in common:
        try:
            ssid_hash = git_file_hash(ssid_repo, ssid_ref, f)
            oc_hash = git_file_hash(opencore_repo, opencore_ref, f)
            if ssid_hash != oc_hash:
                drift_items.append(
                    {
                        "file": f,
                        "type": "content_mismatch",
                        "detail": f"SHA256 differs: ssid={ssid_hash[:12]}... oc={oc_hash[:12]}...",
                    }
                )
        except RuntimeError:
            drift_items.append(
                {
                    "file": f,
                    "type": "comparison_error",
                    "detail": "Could not read file from one or both repos",
                }
            )

    # 4. Files that SHOULD be in open-core (per allowlist) but are missing
    missing_from_oc: list[dict[str, str]] = []
    if allow_prefixes:
        for f in sorted(ssid_files - oc_files):
            if is_in_allow_prefixes(f, allow_prefixes) and not is_denied_by_glob(f, deny_globs):
                missing_from_oc.append(
                    {
                        "file": f,
                        "type": "missing_in_opencore",
                        "detail": "Allowed by policy but absent from open-core",
                    }
                )

    has_drift = bool(drift_items) or bool(policy_violations) or bool(missing_from_oc)

    report = {
        "generated_utc": utc_now(),
        "tool": "opencore_drift_sentinel",
        "version": "1.0.0",
        "status": "DRIFT_DETECTED" if has_drift else "CLEAN",
        "exit_code": EXIT_DRIFT if has_drift else EXIT_CLEAN,
        "ssid_commit": ssid_sha,
        "opencore_commit": oc_sha,
        "ssid_file_count": len(ssid_files),
        "opencore_file_count": len(oc_files),
        "common_file_count": len(common),
        "summary": {
            "content_mismatches": sum(1 for d in drift_items if d["type"] == "content_mismatch"),
            "orphaned_in_opencore": len(orphaned),
            "missing_in_opencore": len(missing_from_oc),
            "policy_violations": len(policy_violations),
        },
        "drift_items": drift_items,
        "missing_in_opencore": missing_from_oc[:100],
        "policy_violations": policy_violations,
    }
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="opencore_drift_sentinel",
        description="Detect drift between SSID and SSID-open-core.",
    )
    p.add_argument(
        "--ssid-repo",
        default=str(Path(__file__).resolve().parents[2]),
        help="Path to SSID repo root",
    )
    p.add_argument(
        "--opencore-repo",
        required=True,
        help="Path to SSID-open-core repo root",
    )
    p.add_argument(
        "--policy",
        default=DEFAULT_POLICY,
        help="Export policy YAML (repo-relative or absolute)",
    )
    p.add_argument(
        "--allowlist",
        default=DEFAULT_ALLOWLIST,
        help="Allowlist YAML (repo-relative or absolute)",
    )
    p.add_argument("--ssid-ref", default="HEAD", help="SSID git ref (default: HEAD)")
    p.add_argument("--opencore-ref", default="HEAD", help="Open-core git ref (default: HEAD)")
    p.add_argument("--output-file", default=None, help="Write JSON report to file instead of stdout")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ssid_repo = Path(args.ssid_repo).resolve()
    opencore_repo = Path(args.opencore_repo).resolve()

    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = ssid_repo / policy_path
    if not policy_path.exists():
        print(f"ERROR: policy not found: {policy_path}", file=sys.stderr)
        return EXIT_ERROR

    allowlist_path = Path(args.allowlist)
    if not allowlist_path.is_absolute():
        allowlist_path = ssid_repo / allowlist_path
    if not allowlist_path.exists():
        allowlist_path = None

    try:
        report = detect_drift(
            ssid_repo=ssid_repo,
            opencore_repo=opencore_repo,
            policy_path=policy_path,
            allowlist_path=allowlist_path,
            ssid_ref=args.ssid_ref,
            opencore_ref=args.opencore_ref,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"

    if args.output_file:
        Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_file).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output_file}")
    else:
        print(output)

    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
