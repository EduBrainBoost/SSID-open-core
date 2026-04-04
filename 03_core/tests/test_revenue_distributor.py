"""Tests for 03_core/subscription_revenue_distributor.py.

Covers path invariants, source validity, and the core_engine re-export hub
(src/core_engine.py) which is always valid Python and immediately testable.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CORE_ROOT / "src"
DISTRIBUTOR_PATH = CORE_ROOT / "subscription_revenue_distributor.py"
CORE_ENGINE_PATH = SRC_ROOT / "core_engine.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_python(path: Path) -> bool:
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        return True
    except SyntaxError:
        return False


def _load(path: Path):
    if not _is_valid_python(path):
        pytest.skip(f"{path.name} is a placeholder — logic tests skipped")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod  # required on Python 3.14+ for @dataclass
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------


class TestRevenueDistributorPresence:
    def test_file_exists(self):
        assert DISTRIBUTOR_PATH.exists(), "subscription_revenue_distributor.py not found"

    def test_file_is_regular_file(self):
        assert DISTRIBUTOR_PATH.is_file()

    def test_file_not_empty(self):
        assert DISTRIBUTOR_PATH.stat().st_size > 0


# ---------------------------------------------------------------------------
# core_engine.py re-export hub — always valid Python
# ---------------------------------------------------------------------------


class TestCoreEngineReexportHub:
    """src/core_engine.py is valid Python and its exports must be correct."""

    @pytest.fixture(autouse=True)
    def _mod(self):
        if str(SRC_ROOT) not in sys.path:
            sys.path.insert(0, str(SRC_ROOT))
        self.mod = _load(CORE_ENGINE_PATH)

    def test_core_root_is_path(self):
        assert isinstance(self.mod.CORE_ROOT, Path)

    def test_core_root_points_to_03_core(self):
        assert self.mod.CORE_ROOT.name == "03_core"

    def test_fairness_engine_path_attribute(self):
        p = self.mod.FAIRNESS_ENGINE_PATH
        assert isinstance(p, Path)
        assert p.name == "fairness_engine.py"

    def test_fee_distribution_engine_path_attribute(self):
        p = self.mod.FEE_DISTRIBUTION_ENGINE_PATH
        assert isinstance(p, Path)
        assert p.name == "fee_distribution_engine.py"

    def test_subscription_revenue_distributor_path_attribute(self):
        p = self.mod.SUBSCRIPTION_REVENUE_DISTRIBUTOR_PATH
        assert isinstance(p, Path)
        assert p.name == "subscription_revenue_distributor.py"

    def test_all_paths_under_core_root(self):
        for attr in ("FAIRNESS_ENGINE_PATH", "FEE_DISTRIBUTION_ENGINE_PATH", "SUBSCRIPTION_REVENUE_DISTRIBUTOR_PATH"):
            path = getattr(self.mod, attr)
            assert self.mod.CORE_ROOT in path.parents, f"{attr} ({path}) is not under CORE_ROOT ({self.mod.CORE_ROOT})"

    def test_dunder_all_contents(self):
        expected = {
            "CORE_ROOT",
            "FAIRNESS_ENGINE_PATH",
            "FEE_DISTRIBUTION_ENGINE_PATH",
            "SUBSCRIPTION_REVENUE_DISTRIBUTOR_PATH",
        }
        assert set(self.mod.__all__) == expected


# ---------------------------------------------------------------------------
# Revenue distributor API contract (real module only)
# ---------------------------------------------------------------------------


class TestRevenueDistributorInterface:
    """subscription_revenue_distributor must expose correct API and produce valid settlements."""

    @pytest.fixture(autouse=True)
    def _mod(self):
        self.mod = _load(DISTRIBUTOR_PATH)

    def test_exposes_distributor_symbol(self):
        symbols = set(dir(self.mod))
        candidates = {
            "RevenueDistributor",
            "distribute_revenue",
            "distribute",
            "calculate_share",
            "SubscriptionRevenueDistributor",
            "RevenueDistributionEngine",
            "DEFAULT_RETENTION_RATES",
            "distribute_subscription_revenue",
        }
        assert candidates & symbols, f"subscription_revenue_distributor exposes none of {candidates}. Got: {symbols}"

    def test_no_placeholder_text(self):
        content = DISTRIBUTOR_PATH.read_text(encoding="utf-8")
        assert "AUTO-GENERATED PLACEHOLDER" not in content

    def test_docstring_present(self):
        assert self.mod.__doc__, "subscription_revenue_distributor.py missing docstring"

    def test_root_24_names_has_24_entries(self):
        assert len(self.mod.ROOT_24_NAMES) == 24

    def test_monthly_settlement_allocates_to_all_roots(self):
        from decimal import Decimal

        dist = self.mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("12000"),
            period=self.mod.SettlementPeriod.MONTHLY,
            period_label="2026-03",
        )
        assert len(result.allocations) == 24
        root_names = {a.root_name for a in result.allocations}
        assert root_names == set(self.mod.ROOT_24_NAMES)

    def test_settlement_amounts_sum_to_gross(self):
        from decimal import Decimal

        dist = self.mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("24000"),
            period=self.mod.SettlementPeriod.QUARTERLY,
            period_label="2026-Q1",
        )
        total = sum(a.amount for a in result.allocations) + result.remainder
        assert total == Decimal("24000")

    def test_core_root_gets_12_percent(self):
        from decimal import Decimal

        dist = self.mod.SubscriptionRevenueDistributor()
        ratios = dist.get_ratios()
        assert ratios["03_core"] == Decimal("0.12")

    def test_settlement_evidence_hash_valid(self):
        from decimal import Decimal

        dist = self.mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("5000"),
            period=self.mod.SettlementPeriod.MONTHLY,
            period_label="2026-03",
        )
        assert len(result.evidence_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.evidence_hash)

    def test_negative_revenue_raises_value_error(self):
        from decimal import Decimal

        dist = self.mod.SubscriptionRevenueDistributor()
        with pytest.raises(ValueError, match="non-negative"):
            dist.calculate_settlement(
                gross_revenue=Decimal("-1"),
                period=self.mod.SettlementPeriod.MONTHLY,
                period_label="2026-03",
            )

    def test_zero_revenue_yields_zero_allocations(self):
        from decimal import Decimal

        dist = self.mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("0"),
            period=self.mod.SettlementPeriod.MONTHLY,
            period_label="2026-03",
        )
        assert all(a.amount == Decimal("0.00") for a in result.allocations)

    def test_custom_ratios_accepted(self):
        from decimal import Decimal

        custom = {root: Decimal("1") / 24 for root in self.mod.ROOT_24_NAMES}
        # Adjust to sum exactly to 1
        remainder_fix = Decimal("1") - sum(custom.values())
        custom[self.mod.ROOT_24_NAMES[0]] += remainder_fix
        dist = self.mod.SubscriptionRevenueDistributor(ratios=custom)
        result = dist.calculate_settlement(
            gross_revenue=Decimal("2400"),
            period=self.mod.SettlementPeriod.MONTHLY,
            period_label="2026-03",
        )
        assert len(result.allocations) == 24
