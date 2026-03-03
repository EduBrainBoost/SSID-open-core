#!/usr/bin/env python3
"""
SSID CLI Wrapper - Enforces Data Minimization
Sets environment variables to disable telemetry/history for all CLI calls.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DATA_MINIMIZATION_ENVVARS = {
    "NO_PROMPT_PERSIST": "true",
    "NO_STDOUT_PERSIST": "true",
    "NO_TELEMETRY": "true",
    "NO_HISTORY": "true",
    "LOG_MODE": "MINIMAL",
    "ANTHROPIC_DISABLE_CACHE": "true",
    "OPENAI_API_KEY": "",
    "GITHUB_TOKEN": "",
}

def apply_data_minimization_env():
    """Apply data minimization environment variables."""
    env = os.environ.copy()
    for key, value in DATA_MINIMIZATION_ENVVARS.items():
        env[key] = value
    return env

def wrap_cli(command: list[str], extra_env: dict | None = None) -> int:
    """Run a CLI command with data minimization enforced."""
    env = apply_data_minimization_env()
    if extra_env:
        env.update(extra_env)

    try:
        result = subprocess.run(command, env=env, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"ERROR: Command not found: {command[0]}")
        return 127

def check_telemetry_disabled() -> bool:
    """Verify telemetry is disabled."""
    for key in DATA_MINIMIZATION_ENVVARS:
        if key in os.environ:
            if os.environ[key] != DATA_MINIMIZATION_ENVVARS.get(key, ""):
                return False
    return True

def main() -> int:
    """Main wrapper entry point."""
    if len(sys.argv) < 2:
        print("Usage: ssid_wrapper <command> [args...]")
        print(f"Data Minimization Enforced: {list(DATA_MINIMIZATION_ENVVARS.keys())}")
        return 1

    command = sys.argv[1:]
    return wrap_cli(command)

if __name__ == "__main__":
    raise SystemExit(main())
