#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

EXIT_HARD_FAIL = 24
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
TOOL_VERSION = "2.0.0"
MANIFEST_SCHEMA_VERSION = "2.0.0"


def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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


def ts_slug(ts: str) -> str:
    return (
        ts.replace("-", "")
        .replace(":", "")
        .replace("T", "T")
        .replace("Z", "Z")
    )


def write_worm_export_evidence(
    repo_root: Path,
    *,
    timestamp_utc: str,
    source_commit: str,
    zip_sha256: str,
    policy_sha256: str,
    deny_globs: list[str],
    file_count: int,
    status: str,
) -> Path:
    worm_dir = (
        repo_root
        / "02_audit_logging"
        / "storage"
        / "worm"
        / "OPENCORERELEASE"
        / ts_slug(timestamp_utc)
    )
    worm_dir.mkdir(parents=True, exist_ok=True)
    out = worm_dir / "export_evidence.json"
    payload = {
        "timestamp_utc": timestamp_utc,
        "source_commit": source_commit,
        "zip_sha256": zip_sha256,
        "policy_sha256": policy_sha256,
        "deny_globs": deny_globs,
        "file_count": file_count,
        "tool_version": TOOL_VERSION,
        "status": status,
    }
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def git(repo_root: Path, args: list[str], text: bool = True) -> str | bytes:
    cmd = ["git", "-C", str(repo_root), *args]
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=text,
    )
    if proc.returncode != 0:
        stderr = proc.stderr if text else proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git command failed: {' '.join(cmd)}\n{stderr.strip()}")
    return proc.stdout if text else proc.stdout


def load_policy(policy_path: Path) -> dict[str, Any]:
    data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    deny_globs = data.get("deny_globs", []) or []
    secret_scan_regex = data.get("secret_scan_regex", []) or []
    if not isinstance(deny_globs, list) or not all(isinstance(v, str) for v in deny_globs):
        raise ValueError("policy deny_globs must be a list[str]")
    if not isinstance(secret_scan_regex, list) or not all(
        isinstance(v, str) for v in secret_scan_regex
    ):
        raise ValueError("policy secret_scan_regex must be a list[str]")
    return data


def is_denied(path_posix: str, deny_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_posix, pattern) for pattern in deny_globs)


def is_allowed_prefix(path_posix: str, allow_prefixes: list[str]) -> bool:
    """Check if path starts with one of the allowed prefixes."""
    if not allow_prefixes:
        return True  # no allowlist = allow all (backward compat)
    return any(path_posix.startswith(prefix) or path_posix == prefix.rstrip("/") for prefix in allow_prefixes)


def is_allowed_extension(path_posix: str, allow_extensions: list[str]) -> bool:
    """Check if file extension is in the allowed list."""
    if not allow_extensions:
        return True  # no extension allowlist = allow all (backward compat)
    suffix = PurePosixPath(path_posix).suffix.lower()
    # files without extension (e.g. Makefile, LICENSE) are allowed
    if not suffix:
        return True
    return suffix in allow_extensions


def compile_secret_patterns(raw_patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in raw_patterns]


def secret_hits_for_content(
    path_posix: str, content: bytes, patterns: list[re.Pattern[str]]
) -> list[dict[str, str]]:
    text = content.decode("utf-8", errors="replace")
    hits: list[dict[str, str]] = []
    for pattern in patterns:
        if pattern.search(text):
            hits.append({"path": path_posix, "pattern": pattern.pattern})
    return hits


def export_filtered_archive(
    repo_root: Path,
    output_dir: Path,
    commit_ref: str,
    policy_path: Path,
    *,
    target_ref: str = "",
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    deny_globs = policy.get("deny_globs", []) or []
    allow_prefixes = policy.get("allow_prefixes", []) or []
    allow_extensions = policy.get("allow_extensions", []) or []
    max_file_size = policy.get("max_file_size_bytes", 0) or 0
    secret_patterns = compile_secret_patterns(policy.get("secret_scan_regex", []) or [])
    policy_version = policy.get("schema_version", "unknown")

    source_commit = str(git(repo_root, ["rev-parse", commit_ref]).strip())
    short_commit = source_commit[:7]
    zip_name = f"SSID_OPENCORERELEASE_{short_commit}.zip"
    zip_path = output_dir / zip_name
    sha_path = output_dir / f"{zip_name}.SHA256.txt"
    manifest_path = output_dir / f"{zip_name}.manifest.json"

    tracked_files_raw = str(git(repo_root, ["ls-tree", "-r", "--name-only", source_commit]))
    tracked_files = [p.strip() for p in tracked_files_raw.splitlines() if p.strip()]

    included: list[str] = []
    excluded_entries: list[dict[str, str]] = []
    secret_hits: list[dict[str, str]] = []
    file_bytes: dict[str, bytes] = {}
    file_hashes: dict[str, str] = {}
    file_sizes: dict[str, int] = {}
    file_provenance: dict[str, dict[str, Any]] = {}

    policy_rel_posix = policy_path.resolve().relative_to(repo_root).as_posix()

    for rel_path in tracked_files:
        rel_posix = rel_path.replace("\\", "/")

        # --- Gate 1: allow_prefixes ---
        if not is_allowed_prefix(rel_posix, allow_prefixes):
            excluded_entries.append({"path": rel_posix, "reason": "not_in_allow_prefixes"})
            continue

        # --- Gate 2: deny_globs ---
        if is_denied(rel_posix, deny_globs):
            excluded_entries.append({"path": rel_posix, "reason": "deny_glob_match"})
            continue

        # --- Gate 3: allow_extensions ---
        if not is_allowed_extension(rel_posix, allow_extensions):
            excluded_entries.append({"path": rel_posix, "reason": "extension_not_allowed"})
            continue

        blob = git(repo_root, ["show", f"{source_commit}:{rel_posix}"], text=False)
        blob_bytes = blob if isinstance(blob, bytes) else blob.encode("utf-8")

        # --- Gate 4: max file size ---
        if max_file_size > 0 and len(blob_bytes) > max_file_size:
            excluded_entries.append({"path": rel_posix, "reason": "oversized"})
            continue

        file_bytes[rel_posix] = blob_bytes
        file_hashes[rel_posix] = sha256_bytes(blob_bytes)
        file_sizes[rel_posix] = len(blob_bytes)
        file_provenance[rel_posix] = {
            "status": "unchanged",
            "public_safe": True,
            "sanitization_rule": None,
            "policy_ref": policy_path.name,
        }
        included.append(rel_posix)

        if rel_posix != policy_rel_posix:
            secret_hits.extend(secret_hits_for_content(rel_posix, blob_bytes, secret_patterns))

    if secret_hits:
        fail_ts = utc_now()
        policy_sha = sha256_file(policy_path)
        worm_evidence = write_worm_export_evidence(
            repo_root,
            timestamp_utc=fail_ts,
            source_commit=source_commit,
            zip_sha256="",
            policy_sha256=policy_sha,
            deny_globs=deny_globs,
            file_count=len(included),
            status="SECRET_SCAN_FAIL",
        )
        payload = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_utc": fail_ts,
            "status": "SECRET_SCAN_FAIL",
            "source_commit": source_commit,
            "policy_file": policy_path.as_posix(),
            "policy_sha256": policy_sha,
            "worm_evidence_path": worm_evidence.relative_to(repo_root).as_posix(),
            "hits": secret_hits,
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        raise SystemExit(EXIT_HARD_FAIL)

    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for rel_posix in sorted(included):
            info = zipfile.ZipInfo(filename=rel_posix, date_time=ZIP_TIMESTAMP)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, file_bytes[rel_posix])

    zip_sha256 = sha256_file(zip_path)
    sha_path.write_text(f"{zip_sha256}  {zip_name}\n", encoding="utf-8")
    pass_ts = utc_now()
    policy_sha = sha256_file(policy_path)
    worm_evidence = write_worm_export_evidence(
        repo_root,
        timestamp_utc=pass_ts,
        source_commit=source_commit,
        zip_sha256=zip_sha256,
        policy_sha256=policy_sha,
        deny_globs=deny_globs,
        file_count=len(included),
        status="PASS",
    )

    # --- Build standardized export manifest ---
    manifest_payload: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_utc": pass_ts,
        "status": "PASS",
        "source_repo": policy.get("source_repo", ""),
        "source_ref": source_commit,
        "target_repo": policy.get("target_repo", ""),
        "target_ref": target_ref or "",
        "policy_file": policy_rel_posix,
        "policy_version": policy_version,
        "policy_sha256": policy_sha,
        "tool_version": TOOL_VERSION,
        "deny_globs": deny_globs,
        "allow_prefixes": allow_prefixes,
        "allow_extensions": allow_extensions,
        "max_file_size_bytes": max_file_size,
        "secret_scan_exempt_paths": [policy_rel_posix],
        "secret_scan_regex": [p.pattern for p in secret_patterns],
        "worm_evidence_path": worm_evidence.relative_to(repo_root).as_posix(),
        "counts": {
            "tracked_files": len(tracked_files),
            "included_files": len(included),
            "excluded_files": len(excluded_entries),
        },
        "files": [
            {
                "path": rel_posix,
                "sha256": file_hashes[rel_posix],
                "size_bytes": file_sizes[rel_posix],
                "sanitized": file_provenance[rel_posix]["status"] == "redacted",
                "provenance": file_provenance[rel_posix],
            }
            for rel_posix in sorted(included)
        ],
        "excluded_files": sorted(excluded_entries, key=lambda e: e["path"]),
        "bundle_sha256": zip_sha256,
        "zip_artifact": zip_name,
        "sha256_file": sha_path.name,
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "zip_path": zip_path,
        "sha_path": sha_path,
        "manifest_path": manifest_path,
        "worm_evidence_path": worm_evidence,
        "zip_sha256": zip_sha256,
        "policy_sha256": policy_sha,
        "source_commit": source_commit,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_opencore_filtered.py",
        description="Create deterministic OpenCore export ZIP from an SSID commit.",
    )
    parser.add_argument("--commit", default="HEAD", help="source commit (default: HEAD)")
    parser.add_argument(
        "--policy",
        default="16_codex/opencore_export_policy.yaml",
        help="export policy file path (repo-relative or absolute)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="output directory for ZIP, SHA256, and manifest JSON",
    )
    parser.add_argument(
        "--outdir",
        default=None,
        help="alias for --output-dir (runbook compatibility)",
    )
    parser.add_argument(
        "--target-ref",
        default="",
        help="target repo ref/branch (metadata only)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="repository root path (for testing or external invocation)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    selected_output_dir = args.outdir if args.outdir is not None else args.output_dir
    output_dir = Path(selected_output_dir).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo_root / policy_path
    if not policy_path.exists():
        print(f"ERROR: policy file not found: {policy_path.as_posix()}", file=sys.stderr)
        return EXIT_HARD_FAIL

    try:
        result = export_filtered_archive(
            repo_root=repo_root,
            output_dir=output_dir,
            commit_ref=args.commit,
            policy_path=policy_path,
            target_ref=args.target_ref,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_HARD_FAIL
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return EXIT_HARD_FAIL

    print(f"SOURCE_COMMIT={result['source_commit']}")
    print(f"ZIP={Path(result['zip_path']).as_posix()}")
    print(f"SHA256={result['zip_sha256']}")
    print(f"POLICY_SHA256={result['policy_sha256']}")
    print(f"SHA_FILE={Path(result['sha_path']).as_posix()}")
    print(f"MANIFEST={Path(result['manifest_path']).as_posix()}")
    print(f"WORM_EVIDENCE={Path(result['worm_evidence_path']).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
