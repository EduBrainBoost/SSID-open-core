# DEPRECATED: LEGACY — Canonical tool is 12_tooling/scripts/promote_to_canonical.py
# Dependencies: 11_test_simulation/tests_compliance/test_extension_allowlist_strict.py,
#   24_meta_orchestration/dispatcher/e2e_dispatcher.py
#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "12_tooling" / "scripts" / "deterministic_repo_setup.py"
runpy.run_path(SCRIPT.as_posix(), run_name="__main__")
