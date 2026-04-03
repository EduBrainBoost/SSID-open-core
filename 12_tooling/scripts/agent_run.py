#!/usr/bin/env python3
"""AGENT 03 — Agent Run Wrapper for MAOS Enforcement.

Wraps individual agent execution with enforcement checks:
1. Runs sot_validator.py --verify-all before agent execution
2. Validates write boundary (scratch outside repo)
3. Appends to WORKLOG.jsonl after completion
4. Logs registry_event

This script is the canonical entry point for all agent runs.
The dispatcher in 24_meta_orchestration must call this wrapper
instead of invoking agents directly.

SoT v4.1.0 | ROOT-24-LOCK | Classification: Orchestration
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOT_VALIDATOR = REPO_ROOT / "12_tooling" / "cli" / "sot_validator.py"
WORKLOG_PATH = REPO_ROOT / "24_meta_orchestration" / "registry" / "WORKLOG.jsonl"
REGISTRY_EVENTS_PATH = REPO_ROOT / "24_meta_orchestration" / "registry" / "registry_events.log.jsonl"


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _append_jsonl(path: Path, entry: dict) -> None:
    """Append a single JSON line to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")


def run_sot_validation() -> tuple[bool, str]:
    """Run sot_validator --verify-all. Returns (passed, output)."""
    if not SOT_VALIDATOR.exists():
        return False, f"sot_validator not found at {SOT_VALIDATOR}"

    result = subprocess.run(
        [sys.executable, str(SOT_VALIDATOR), "--verify-all"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        timeout=120,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def validate_scratch_boundary(scratch_dir: str) -> bool:
    """Ensure scratch directory is outside the repo."""
    scratch = Path(scratch_dir).resolve()
    repo = REPO_ROOT.resolve()

    # Scratch must not be inside repo
    try:
        scratch.relative_to(repo)
        return False  # scratch is inside repo = violation
    except ValueError:
        return True  # scratch is outside repo = OK


def main() -> int:
    parser = argparse.ArgumentParser(description="MAOS Agent Run Wrapper")
    parser.add_argument("--agent-id", required=True, help="Agent identifier")
    parser.add_argument("--command", required=True, help="Command to execute")
    parser.add_argument(
        "--scratch-dir",
        default=tempfile.gettempdir(),
        help="Scratch directory (must be outside repo)",
    )
    parser.add_argument(
        "--skip-sot-check",
        action="store_true",
        help="Skip SoT validation (for emergency use only)",
    )
    args = parser.parse_args()

    agent_id = args.agent_id
    ts_start = _ts()

    # Step 1: SoT validation
    if not args.skip_sot_check:
        print(f"[MAOS] Running SoT validation for agent {agent_id} ...")
        sot_passed, sot_output = run_sot_validation()
        if not sot_passed:
            print(f"[MAOS] SoT validation FAILED — agent {agent_id} blocked")
            print(sot_output[:500])
            _append_jsonl(WORKLOG_PATH, {
                "timestamp": ts_start,
                "agent_id": agent_id,
                "event": "sot_validation_failed",
                "status": "blocked",
            })
            return 1
        print("[MAOS] SoT validation PASSED")

    # Step 2: Scratch boundary check
    if not validate_scratch_boundary(args.scratch_dir):
        print(f"[MAOS] Scratch directory violation: {args.scratch_dir} is inside repo")
        _append_jsonl(WORKLOG_PATH, {
            "timestamp": ts_start,
            "agent_id": agent_id,
            "event": "scratch_boundary_violation",
            "scratch_dir": args.scratch_dir,
            "status": "blocked",
        })
        return 1

    # Step 3: Execute agent command
    print(f"[MAOS] Executing agent {agent_id}: {args.command}")
    env = os.environ.copy()
    env["SSID_SCRATCH_DIR"] = args.scratch_dir
    env["SSID_AGENT_ID"] = agent_id

    result = subprocess.run(
        args.command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=600,
    )

    ts_end = _ts()
    status = "success" if result.returncode == 0 else "failed"

    # Step 4: Append WORKLOG entry
    worklog_entry = {
        "timestamp": ts_end,
        "agent_id": agent_id,
        "event": "agent_run_complete",
        "command": args.command,
        "status": status,
        "return_code": result.returncode,
        "duration_started": ts_start,
        "duration_ended": ts_end,
        "stdout_hash": _sha256(result.stdout) if result.stdout else None,
        "stderr_hash": _sha256(result.stderr) if result.stderr else None,
    }
    _append_jsonl(WORKLOG_PATH, worklog_entry)

    # Step 5: Registry event
    registry_event = {
        "timestamp": ts_end,
        "event_type": "agent_execution",
        "agent_id": agent_id,
        "status": status,
        "evidence_hash": _sha256(json.dumps(worklog_entry, sort_keys=True)),
    }
    _append_jsonl(REGISTRY_EVENTS_PATH, registry_event)

    # Output agent stdout/stderr
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)

    print(f"[MAOS] Agent {agent_id} completed: {status}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
