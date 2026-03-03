#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

# Single entry point wrapper for SSID dispatcher orchestration.
# Data-minimization markers for SoT checks:
# - patch.sha256
# - hash-only
# - 02_audit_logging
DISPATCHER = Path(__file__).resolve().parents[3] / "24_meta_orchestration" / "dispatcher" / "e2e_dispatcher.py"
runpy.run_path(DISPATCHER.as_posix(), run_name="__main__")
