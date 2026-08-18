#!/usr/bin/env python3
"""Detects drift between baseline and working tree. Exit 0=PASS, 24=FAIL."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
def main():
    r = subprocess.run(["git","diff","--name-only"], capture_output=True, text=True, cwd=str(REPO))
    if r.stdout.strip():
        changed = r.stdout.strip().splitlines()
        print(f"FAIL: baseline_drift_guard: {len(changed)} files: {changed[:5]}", file=sys.stderr); return 24
    print("PASS: baseline_drift_guard"); return 0
if __name__ == "__main__": raise SystemExit(main())
