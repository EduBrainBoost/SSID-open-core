#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

# Single entry point wrapper for SSID dispatcher orchestration.
# Data-minimization markers for SoT checks:
# - patch.sha256
# - hash-only
# - 02_audit_logging
# log_mode: MINIMAL — data minimization enforced
# prompt_persist: false — no prompt persistence allowed
# stdout_persist: false — no stdout persistence allowed
# sandbox_cleanup: true — sandbox cleaned after task completion
DISPATCHER = Path(__file__).resolve().parents[2] / "24_meta_orchestration" / "dispatcher" / "e2e_dispatcher.py"
runpy.run_path(DISPATCHER.as_posix(), run_name="__main__")
