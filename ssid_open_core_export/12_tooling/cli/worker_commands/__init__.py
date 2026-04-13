"""SSIDCTL Worker Command Modules.

Canonical runtime worker commands for the 11 SSIDCTL workers:
supervisor, dispatch, build, test, browser, policy, audit, registry, provider, release, repair.

Each module provides:
- main() entry point
- argparse CLI interface
- Structured JSON output on stdout
- Non-zero exit on failure
"""

__version__ = "1.0.0"

WORKER_COMMANDS = [
    "supervisor",
    "dispatch",
    "build",
    "test",
    "browser",
    "policy",
    "audit",
    "registry",
    "provider",
    "release",
    "repair",
]
