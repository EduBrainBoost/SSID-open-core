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
from pathlib import Path
from typing import Any

import yaml

EXIT_HARD_FAIL = 24
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
TOOL_VERSION = "2.0.0"
DEFAULT_ALLOWLIST = "23_compliance/policies/open_core_export_allowlist.yaml"


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return ts.replace("-", "").replace(":", "").replace("T", "T").replace("Z", "Z")


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
    worm_dir = repo_root / "02_audit_logging" / "storage" / "worm" / "OPENCORERELEASE" / ts_slug(timestamp_utc)
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
    if not isinstance(secret_scan_regex, list) or not all(isinstance(v, str) for v in secret_scan_regex):
        raise ValueError("policy secret_scan_regex must be a list[str]")
    return data


def load_allowlist(allowlist_path: Path) -> dict[str, Any]:
    data = yaml.safe_load(allowlist_path.read_text(encoding="utf-8")) or {}
    root_files = data.get("root_files", []) or []
    allowed_paths = data.get("allowed_paths", []) or []
    data.get("denied_patterns", []) or []
    if not isinstance(root_files, list):
        raise ValueError("allowlist root_files must be a list")
    if not isinstance(allowed_paths, list):
        raise ValueError("allowlist allowed_paths must be a list")
    return data


def is_allowed(path_posix: str, allowlist: dict[str, Any], extra_allowed: set[str]) -> bool:
    if path_posix in extra_allowed:
        return True
    root_files = set(allowlist.get("root_files", []) or [])
    if "/" not in path_posix and path_posix in root_files:
        return True
    allowed_paths = allowlist.get("allowed_paths", []) or []
    for prefix in allowed_paths:
        prefix_clean = prefix.rstrip("/") + "/"
        if path_posix.startswith(prefix_clean) or path_posix == prefix.rstrip("/"):
            return True
    return False


def is_denied(path_posix: str, deny_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_posix, pattern) for pattern in deny_globs)


def matches_denied_patterns(path_posix: str, denied_patterns: list[str]) -> bool:
    basename = path_posix.rsplit("/", 1)[-1] if "/" in path_posix else path_posix
    for pattern in denied_patterns:
        if pattern.endswith("/"):
            if f"/{pattern}" in f"/{path_posix}/" or path_posix.startswith(pattern):
                return True
        elif fnmatch.fnmatch(basename, pattern):
            return True
    return False


def compile_secret_patterns(raw_patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in raw_patterns]


def secret_hits_for_content(path_posix: str, content: bytes, patterns: list[re.Pattern[str]]) -> list[dict[str, str]]:
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
    allowlist_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    deny_globs = policy.get("deny_globs", []) or []
    secret_patterns = compile_secret_patterns(policy.get("secret_scan_regex", []) or [])

    allowlist: dict[str, Any] = {}
    allowlist_rel_posix = ""
    denied_patterns: list[str] = []
    if allowlist_path and allowlist_path.exists():
        allowlist = load_allowlist(allowlist_path)
        allowlist_rel_posix = allowlist_path.resolve().relative_to(repo_root).as_posix()
        denied_patterns = allowlist.get("denied_patterns", []) or []

    source_commit = str(git(repo_root, ["rev-parse", commit_ref]).strip())
    short_commit = source_commit[:7]
    zip_name = f"SSID_OPENCORERELEASE_{short_commit}.zip"
    zip_path = output_dir / zip_name
    sha_path = output_dir / f"{zip_name}.SHA256.txt"
    evidence_path = output_dir / f"{zip_name}.evidence.json"

    tracked_files_raw = str(git(repo_root, ["ls-tree", "-r", "--name-only", source_commit]))
    tracked_files = [p.strip() for p in tracked_files_raw.splitlines() if p.strip()]

    included: list[str] = []
    excluded: list[str] = []
    not_allowed: list[str] = []
    denied_by_pattern: list[str] = []
    secret_hits: list[dict[str, str]] = []
    file_bytes: dict[str, bytes] = {}

    policy_rel_posix = policy_path.resolve().relative_to(repo_root).as_posix()
    extra_allowed = {policy_rel_posix}
    if allowlist_rel_posix:
        extra_allowed.add(allowlist_rel_posix)

    for rel_path in tracked_files:
        rel_posix = rel_path.replace("\\", "/")
        if allowlist and not is_allowed(rel_posix, allowlist, extra_allowed):
            not_allowed.append(rel_posix)
            excluded.append(rel_posix)
            continue
        if is_denied(rel_posix, deny_globs):
            excluded.append(rel_posix)
            continue
        if denied_patterns and matches_denied_patterns(rel_posix, denied_patterns):
            denied_by_pattern.append(rel_posix)
            excluded.append(rel_posix)
            continue
        if not dry_run:
            blob = git(repo_root, ["show", f"{source_commit}:{rel_posix}"], text=False)
            blob_bytes = blob if isinstance(blob, bytes) else blob.encode("utf-8")
            file_bytes[rel_posix] = blob_bytes
        included.append(rel_posix)
        if not dry_run and rel_posix != policy_rel_posix:
            secret_hits.extend(secret_hits_for_content(rel_posix, file_bytes[rel_posix], secret_patterns))

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
            "generated_utc": fail_ts,
            "status": "SECRET_SCAN_FAIL",
            "source_commit": source_commit,
            "policy_file": policy_path.as_posix(),
            "policy_sha256": policy_sha,
            "worm_evidence_path": worm_evidence.relative_to(repo_root).as_posix(),
            "hits": secret_hits,
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        raise SystemExit(EXIT_HARD_FAIL)

    if dry_run:
        allowlist_sha = sha256_file(allowlist_path) if allowlist_path and allowlist_path.exists() else ""
        dry_manifest = {
            "generated_utc": utc_now(),
            "status": "DRY_RUN",
            "source_commit": source_commit,
            "tool_version": TOOL_VERSION,
            "allowlist_file": allowlist_rel_posix,
            "allowlist_sha256": allowlist_sha,
            "policy_file": policy_rel_posix,
            "counts": {
                "tracked_files": len(tracked_files),
                "included_files": len(included),
                "excluded_not_allowed": len(not_allowed),
                "excluded_deny_globs": len(excluded) - len(not_allowed) - len(denied_by_pattern),
                "excluded_deny_patterns": len(denied_by_pattern),
            },
            "included_files": sorted(included),
            "not_allowed_files": sorted(not_allowed)[:50],
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / f"SSID_OPENCORERELEASE_{short_commit}.dry_run.json"
        manifest_path.write_text(
            json.dumps(dry_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return {
            "zip_path": manifest_path,
            "sha_path": manifest_path,
            "evidence_path": manifest_path,
            "worm_evidence_path": manifest_path,
            "zip_sha256": "",
            "policy_sha256": sha256_file(policy_path),
            "source_commit": source_commit,
            "dry_run": True,
            "included_count": len(included),
            "excluded_count": len(excluded),
        }

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
    allowlist_sha = sha256_file(allowlist_path) if allowlist_path and allowlist_path.exists() else ""
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

    evidence_payload = {
        "generated_utc": pass_ts,
        "status": "PASS",
        "source_repo": policy.get("source_repo"),
        "target_repo": policy.get("target_repo"),
        "mode": policy.get("mode"),
        "source_commit": source_commit,
        "source_commit_short": short_commit,
        "policy_file": policy_path.as_posix(),
        "policy_sha256": policy_sha,
        "allowlist_file": allowlist_rel_posix,
        "allowlist_sha256": allowlist_sha,
        "deny_globs": deny_globs,
        "denied_patterns": denied_patterns,
        "secret_scan_exempt_paths": [policy_rel_posix],
        "secret_scan_regex": [p.pattern for p in secret_patterns],
        "tool_version": TOOL_VERSION,
        "worm_evidence_path": worm_evidence.relative_to(repo_root).as_posix(),
        "counts": {
            "tracked_files": len(tracked_files),
            "included_files": len(included),
            "excluded_not_allowed": len(not_allowed),
            "excluded_deny_globs": len(excluded) - len(not_allowed) - len(denied_by_pattern),
            "excluded_deny_patterns": len(denied_by_pattern),
            "total_excluded": len(excluded),
        },
        "excluded_files": sorted(excluded),
        "zip_artifact": zip_name,
        "zip_sha256": zip_sha256,
        "sha256_file": sha_path.name,
    }
    evidence_path.write_text(
        json.dumps(evidence_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "zip_path": zip_path,
        "sha_path": sha_path,
        "evidence_path": evidence_path,
        "worm_evidence_path": worm_evidence,
        "zip_sha256": zip_sha256,
        "policy_sha256": policy_sha,
        "source_commit": source_commit,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_opencore_filtered.py",
        description="Create deterministic OpenCore export ZIP from an SSID commit (allow-only).",
    )
    parser.add_argument("--commit", default="HEAD", help="source commit (default: HEAD)")
    parser.add_argument(
        "--policy",
        default="16_codex/opencore_export_policy.yaml",
        help="deny/secret policy file path (repo-relative or absolute)",
    )
    parser.add_argument(
        "--allowlist",
        default=DEFAULT_ALLOWLIST,
        help="allowlist file path (repo-relative or absolute, default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="output directory for ZIP, SHA256, and evidence JSON",
    )
    parser.add_argument(
        "--outdir",
        default=None,
        help="alias for --output-dir (runbook compatibility)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="repository root path (for testing or external invocation)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="output manifest JSON without creating ZIP (verify allowlist scope)",
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

    allowlist_path = Path(args.allowlist)
    if not allowlist_path.is_absolute():
        allowlist_path = repo_root / allowlist_path
    if not allowlist_path.exists():
        print(f"ERROR: allowlist file not found: {allowlist_path.as_posix()}", file=sys.stderr)
        return EXIT_HARD_FAIL

    try:
        result = export_filtered_archive(
            repo_root=repo_root,
            output_dir=output_dir,
            commit_ref=args.commit,
            policy_path=policy_path,
            allowlist_path=allowlist_path,
            dry_run=args.dry_run,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_HARD_FAIL
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return EXIT_HARD_FAIL

    if args.dry_run:
        print("DRY_RUN=true")
        print(f"SOURCE_COMMIT={result['source_commit']}")
        print(f"INCLUDED={result['included_count']}")
        print(f"EXCLUDED={result['excluded_count']}")
        print(f"MANIFEST={Path(result['zip_path']).as_posix()}")
    else:
        print(f"SOURCE_COMMIT={result['source_commit']}")
        print(f"ZIP={Path(result['zip_path']).as_posix()}")
        print(f"SHA256={result['zip_sha256']}")
        print(f"POLICY_SHA256={result['policy_sha256']}")
        print(f"SHA_FILE={Path(result['sha_path']).as_posix()}")
        print(f"EVIDENCE={Path(result['evidence_path']).as_posix()}")
        print(f"WORM_EVIDENCE={Path(result['worm_evidence_path']).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
