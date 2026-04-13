"""core_engine — Re-export hub for 03_core root-level engines.

This module provides a single import point for the three canonical
engines that live at the 03_core root level:
  - fairness_engine
  - fee_distribution_engine
  - subscription_revenue_distributor

It does NOT duplicate business logic; it only exposes path references
and lazy imports so downstream code can do::

    from src.core_engine import CORE_ROOT
"""

from __future__ import annotations

from pathlib import Path

# Canonical root of the 03_core module (one level up from src/).
CORE_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Engine path references (safe for import-time checks without executing them)
# ---------------------------------------------------------------------------
FAIRNESS_ENGINE_PATH = CORE_ROOT / "fairness_engine.py"
FEE_DISTRIBUTION_ENGINE_PATH = CORE_ROOT / "fee_distribution_engine.py"
SUBSCRIPTION_REVENUE_DISTRIBUTOR_PATH = CORE_ROOT / "subscription_revenue_distributor.py"

__all__ = [
    "CORE_ROOT",
    "FAIRNESS_ENGINE_PATH",
    "FEE_DISTRIBUTION_ENGINE_PATH",
    "SUBSCRIPTION_REVENUE_DISTRIBUTOR_PATH",
]
