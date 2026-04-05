"""conftest.py — ensures the engines package is importable for all test_engines tests."""
from __future__ import annotations

import sys
from pathlib import Path

# 03_core/engines must be on sys.path for direct module imports in tests.
ENGINES_DIR = Path(__file__).resolve().parents[2] / "engines"
if str(ENGINES_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINES_DIR))
