"""Configure Python path for SWS test imports."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
_core_path = str(REPO_ROOT / "03_core")
if _core_path not in sys.path:
    sys.path.insert(0, _core_path)

# Force import of sws package from 03_core so submodule resolution works
import importlib
if "sws" in sys.modules:
    importlib.reload(sys.modules["sws"])
