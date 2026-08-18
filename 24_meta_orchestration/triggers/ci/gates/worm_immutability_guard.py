#!/usr/bin/env python3
"""Ensures WORM storage files are never modified. Exit 0=PASS, 24=FAIL."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORM_PREFIX = "02_audit_logging/storage/worm/"
def main():
    r = subprocess.run(["git","diff","--cached","--diff-filter=M","--name-only"], capture_output=True, text=True, cwd=str(REPO))
    worm = [f for f in (r.stdout.strip().splitlines() if r.stdout.strip() else []) if f.startswith(WORM_PREFIX)]
    if worm: print(f"FAIL: worm_immutability_guard: {worm}", file=sys.stderr); return 24
    print("PASS: worm_immutability_guard"); return 0
if __name__ == "__main__": raise SystemExit(main())
