"""Deterministic run_id computation for E2E pipeline."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def get_git_sha(repo_root: Path) -> str:
    """Return current HEAD sha (full 40 chars)."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def compute_run_id(
    git_sha: str,
    task_id: str,
    root_id: str,
    shard_id: str,
    action: str,
    inputs_hash: str,
) -> str:
    """Canonical run_id = sha256(git_sha + task_id + root_id + shard_id + action + inputs_hash)[:16]"""
    payload = git_sha + task_id + root_id + shard_id + action + inputs_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compute_file_sha256(path: Path) -> str:
    """SHA256 hex digest of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
