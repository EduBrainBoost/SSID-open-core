#!/usr/bin/env python3
"""Blocks writes to denied paths. Exit 0=PASS, 24=FAIL."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DENYLIST = [".env", "credentials", "private_key", ".secret"]
def main():
    r = subprocess.run(["git","diff","--cached","--name-only"], capture_output=True, text=True, cwd=str(REPO))
    staged = [f.strip() for f in r.stdout.splitlines() if f.strip()]
    v = [f for f in staged if any(d in f.lower() for d in DENYLIST)]
    if v: print(f"FAIL: write_boundary_denylist_guard: {v}", file=sys.stderr); return 24
    print("PASS: write_boundary_denylist_guard"); return 0
if __name__ == "__main__": raise SystemExit(main())
