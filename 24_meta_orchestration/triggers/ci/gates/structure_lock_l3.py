#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    p = subprocess.run([sys.executable, "12_tooling/scripts/structure_guard.py"], capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
