#!/usr/bin/env python3
"""EMS Bridge — deterministic wrapper for ssidctl from SSID repo.

Calls ssidctl with fixed paths (SSID repo, EMS state/evidence roots, limits)
so that SSID consumers can invoke EMS autopilot/attest without manual
path configuration or copy/paste.

Usage:
    python ems_bridge.py attest              # Integrity/existence check
    python ems_bridge.py autopilot <task-id> # Bounded autopilot run
    python ems_bridge.py status <run-id>     # Check run status

All paths are derived from the canonical layout (via ENV or default):
    SSID:       $SSID_PATH (required, or set WORKSPACE_ROOT)
    SSID-EMS:   $EMS_REPO_PATH (required, or set WORKSPACE_ROOT)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# ── Canonical paths (required via ENV) ──────────────────────────────────
# Set SSID_PATH and EMS_REPO_PATH environment variables, or WORKSPACE_ROOT
_workspace = os.environ.get("WORKSPACE_ROOT", "")
SSID_REPO = Path(os.environ.get("SSID_PATH") or f"{_workspace}/SSID" if _workspace else ".")
EMS_REPO = Path(os.environ.get("EMS_REPO_PATH") or f"{_workspace}/SSID-EMS" if _workspace else ".")

# Derived from ems.yaml config
STATE_DIR = EMS_REPO / "state"
EVIDENCE_DIR = EMS_REPO / "evidence"


def _run_ssidctl(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run ssidctl with the given arguments."""
    cmd = [sys.executable, "-m", "ssidctl"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(EMS_REPO),
    )
    if check and result.returncode != 0:
        print(f"ssidctl exited with code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    return result


def cmd_attest() -> int:
    """Run full attestation: rules + policies + plans + agents."""
    print("EMS Bridge: Running attestation...")
    result = _run_ssidctl(["attest", "--all", "--json"], check=False)
    if result.stdout:
        print(result.stdout)
        try:
            data = json.loads(result.stdout)
            verdict = data.get("verdict", "UNKNOWN")
            print(f"Verdict: {verdict}")
        except json.JSONDecodeError:
            pass
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def cmd_autopilot(task_id: str, max_iter: int = 5, run_id: str = "") -> int:
    """Run bounded autopilot loop for a specific task."""
    print(f"EMS Bridge: Starting autopilot run...")
    print(f"  Task ID:    {task_id}")
    print(f"  Max iter:   {max_iter}")

    args = [
        "autopilot", "run",
        "--task-id", task_id,
        "--max-iter", str(max_iter),
    ]
    if run_id:
        args.extend(["--run-id", run_id])
        print(f"  Run ID:     {run_id}")

    print()
    result = _run_ssidctl(args, check=False)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Print evidence locations
    if run_id:
        state_run = STATE_DIR / "runs" / run_id
        evidence_run = EVIDENCE_DIR / "runs" / run_id
        print(f"\nEvidence paths:")
        print(f"  State:    {state_run}")
        print(f"  Evidence: {evidence_run}")

    return result.returncode


def cmd_status(run_id: str) -> int:
    """Check status of a specific autopilot run."""
    result = _run_ssidctl(["autopilot", "status", run_id], check=False)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python ems_bridge.py {attest|autopilot|status} [args]")
        print()
        print("Commands:")
        print("  attest                    Full integrity check (rules, plans, agents)")
        print("  autopilot <task-id>       Bounded autopilot run")
        print("    [--max-iter N]          Max iterations (default: 5)")
        print("    [--run-id ID]           Explicit run ID")
        print("  status <run-id>           Check run status")
        return 1

    command = sys.argv[1]

    if command == "attest":
        return cmd_attest()

    elif command == "autopilot":
        if len(sys.argv) < 3:
            print("Error: task-id required", file=sys.stderr)
            print("Usage: python ems_bridge.py autopilot <task-id> [--max-iter N] [--run-id ID]")
            return 1
        task_id = sys.argv[2]
        max_iter = 5
        run_id = ""
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--max-iter" and i + 1 < len(sys.argv):
                max_iter = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--run-id" and i + 1 < len(sys.argv):
                run_id = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        return cmd_autopilot(task_id, max_iter, run_id)

    elif command == "status":
        if len(sys.argv) < 3:
            print("Error: run-id required", file=sys.stderr)
            return 1
        return cmd_status(sys.argv[2])

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
