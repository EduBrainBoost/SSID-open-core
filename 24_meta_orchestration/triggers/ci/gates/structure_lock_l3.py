#!/usr/bin/env python3
"""Structure Lock L3 Gate — runs structure_guard + fs_noise_detector.

SoT v4.1.0 | ROOT-24-LOCK | Classification: Gate
Updated by AGENT 03/04 — MAOS Enforcement + Anti-Noise
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_GATES_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _GATES_DIR.parents[3]


def _run(script: str, cwd: str | None = None) -> int:
    """Run a Python script, relay output, return exit code."""
    p = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True,
        cwd=cwd or str(_REPO_ROOT),
    )
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    return p.returncode


def main() -> int:
    # Gate 1: Structure guard (ROOT-24-LOCK)
    rc_structure = _run("12_tooling/scripts/structure_guard.py")

    # Gate 2: FS noise detection (Agent 04)
    noise_script = _GATES_DIR / "fs_noise_detector.py"
    rc_noise = _run(str(noise_script)) if noise_script.exists() else 0

    if rc_structure != 0:
        print("STRUCTURE_LOCK_L3_FAIL: structure_guard failed")
        return rc_structure

    if rc_noise != 0:
        print("STRUCTURE_LOCK_L3_FAIL: fs_noise_detector failed")
        return rc_noise

    print("STRUCTURE_LOCK_L3_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
