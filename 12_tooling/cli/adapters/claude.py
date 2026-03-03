#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

DISPATCHER_CLI = Path(__file__).resolve().parents[3] / "12_tooling" / "cli" / "ssid_dispatcher.py"
runpy.run_path(DISPATCHER_CLI.as_posix(), run_name="__main__")
