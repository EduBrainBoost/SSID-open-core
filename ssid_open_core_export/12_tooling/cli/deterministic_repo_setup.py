#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "12_tooling" / "scripts" / "deterministic_repo_setup.py"
runpy.run_path(SCRIPT.as_posix(), run_name="__main__")
