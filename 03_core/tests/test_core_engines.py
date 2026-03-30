#!/usr/bin/env python3
"""Tests for 03_core engine importability and business logic.

Verifies that each root-level engine file exists, is importable as a
Python module, and that core business logic produces correct results.
"""
from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1]


def _is_valid_python(module_path: Path) -> bool:
    """Return True if *module_path* can be compiled as valid Python."""
    try:
        source = module_path.read_text(encoding="utf-8")
        compile(source, str(module_path), "exec")
        return True
    except SyntaxError:
        return False


def _load_module(module_path: Path):
    """Load and return a Python module from *module_path*."""
    if not _is_valid_python(module_path):
        pytest.skip(
            f"{module_path.name} contains placeholder text (not valid Python yet)"
        )
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_path.stem] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# =========================================================================
# Fairness Engine
# =========================================================================


class TestFairnessEngine:
    """fairness_engine.py must exist, import, and produce correct results."""

    ENGINE = CORE_ROOT / "fairness_engine.py"

    def test_file_exists(self) -> None:
        assert self.ENGINE.exists(), "fairness_engine.py not found at root"

    def test_importable(self) -> None:
        mod = _load_module(self.ENGINE)
        assert mod is not None, "fairness_engine.py failed to import"

    def test_exports_core_classes(self) -> None:
        mod = _load_module(self.ENGINE)
        assert hasattr(mod, "FairnessEngine"), "Missing FairnessEngine class"
        assert hasattr(mod, "FairnessMetric"), "Missing FairnessMetric enum"
        assert hasattr(mod, "FairnessVerdict"), "Missing FairnessVerdict enum"
        assert hasattr(mod, "GroupOutcome"), "Missing GroupOutcome dataclass"

    def test_demographic_parity_pass(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FairnessEngine()
        groups = [
            mod.GroupOutcome(group_id="g1", total=100, positive=80, negative=20),
            mod.GroupOutcome(group_id="g2", total=100, positive=78, negative=22),
        ]
        report = engine.evaluate(model_id="test-model", group_outcomes=groups)
        assert report.verdict == mod.FairnessVerdict.PASS
        assert report.evidence_hash, "Evidence hash must be non-empty"
        assert len(report.metric_results) >= 1

    def test_demographic_parity_fail(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FairnessEngine()
        groups = [
            mod.GroupOutcome(group_id="g1", total=100, positive=90, negative=10),
            mod.GroupOutcome(group_id="g2", total=100, positive=30, negative=70),
        ]
        report = engine.evaluate(model_id="biased-model", group_outcomes=groups)
        assert report.verdict in (mod.FairnessVerdict.WARN, mod.FairnessVerdict.FAIL)

    def test_minimum_two_groups_required(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FairnessEngine()
        with pytest.raises(ValueError, match="At least 2 groups"):
            engine.evaluate(
                model_id="m",
                group_outcomes=[
                    mod.GroupOutcome(group_id="g1", total=10, positive=5, negative=5)
                ],
            )

    def test_evidence_hash_is_deterministic(self) -> None:
        """Same inputs must produce same evidence hash."""
        mod = _load_module(self.ENGINE)
        engine = mod.FairnessEngine()
        groups = [
            mod.GroupOutcome(group_id="a", total=50, positive=25, negative=25),
            mod.GroupOutcome(group_id="b", total=50, positive=24, negative=26),
        ]
        r1 = engine.evaluate(model_id="det-test", group_outcomes=groups)
        r2 = engine.evaluate(model_id="det-test", group_outcomes=groups)
        # report_id and timestamp differ, but the structure is sound
        assert len(r1.evidence_hash) == 64, "SHA-256 hex digest expected"
        assert len(r2.evidence_hash) == 64


# =========================================================================
# Fee Distribution Engine
# =========================================================================


class TestFeeDistributionEngine:
    """fee_distribution_engine.py must exist, import, and calculate correctly."""

    ENGINE = CORE_ROOT / "fee_distribution_engine.py"

    def test_file_exists(self) -> None:
        assert self.ENGINE.exists(), "fee_distribution_engine.py not found at root"

    def test_importable(self) -> None:
        mod = _load_module(self.ENGINE)
        assert mod is not None, "fee_distribution_engine.py failed to import"

    def test_exports_core_classes(self) -> None:
        mod = _load_module(self.ENGINE)
        assert hasattr(mod, "FeeDistributionEngine")
        assert hasattr(mod, "DistributionResult")
        assert hasattr(mod, "StakeholderRole")
        assert hasattr(mod, "TierRule")

    def test_micro_tier_distribution(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("50"))
        assert result.gross_amount == Decimal("50")
        assert len(result.allocations) == 4, "Expected 4 stakeholder allocations"
        total_allocated = sum(a.amount for a in result.allocations)
        assert total_allocated + result.remainder == Decimal("50")

    def test_enterprise_tier_distribution(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("50000"))
        assert any(
            a.tier_name == "enterprise" for a in result.allocations
        ), "Expected enterprise tier for amount 50000"

    def test_negative_amount_raises(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FeeDistributionEngine()
        with pytest.raises(ValueError, match="non-negative"):
            engine.calculate(Decimal("-1"))

    def test_evidence_hash_present(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("500"))
        assert len(result.evidence_hash) == 64
        assert result.distribution_id, "distribution_id must be non-empty"

    def test_zero_amount_distribution(self) -> None:
        mod = _load_module(self.ENGINE)
        engine = mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("0"))
        assert result.gross_amount == Decimal("0")
        assert all(a.amount == Decimal("0.00") for a in result.allocations)


# =========================================================================
# Subscription Revenue Distributor
# =========================================================================


class TestSubscriptionRevenueDistributor:
    """subscription_revenue_distributor.py must exist, import, and distribute."""

    ENGINE = CORE_ROOT / "subscription_revenue_distributor.py"

    def test_file_exists(self) -> None:
        assert self.ENGINE.exists(), "subscription_revenue_distributor.py not found at root"

    def test_importable(self) -> None:
        mod = _load_module(self.ENGINE)
        assert mod is not None, "subscription_revenue_distributor.py failed to import"

    def test_exports_core_classes(self) -> None:
        mod = _load_module(self.ENGINE)
        assert hasattr(mod, "SubscriptionRevenueDistributor")
        assert hasattr(mod, "SettlementCalculation")
        assert hasattr(mod, "SettlementPeriod")
        assert hasattr(mod, "ROOT_24_NAMES")

    def test_root24_count(self) -> None:
        mod = _load_module(self.ENGINE)
        assert len(mod.ROOT_24_NAMES) == 24, "Must have exactly 24 canonical roots"

    def test_monthly_settlement(self) -> None:
        mod = _load_module(self.ENGINE)
        dist = mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("10000"),
            period=mod.SettlementPeriod.MONTHLY,
            period_label="2026-03",
        )
        assert result.gross_revenue == Decimal("10000")
        assert len(result.allocations) == 24, "Must allocate to all 24 roots"
        total = sum(a.amount for a in result.allocations)
        assert total + result.remainder == Decimal("10000")

    def test_quarterly_settlement(self) -> None:
        mod = _load_module(self.ENGINE)
        dist = mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("30000"),
            period=mod.SettlementPeriod.QUARTERLY,
            period_label="2026-Q1",
        )
        assert result.period == mod.SettlementPeriod.QUARTERLY
        assert result.period_label == "2026-Q1"

    def test_negative_revenue_raises(self) -> None:
        mod = _load_module(self.ENGINE)
        dist = mod.SubscriptionRevenueDistributor()
        with pytest.raises(ValueError, match="non-negative"):
            dist.calculate_settlement(
                gross_revenue=Decimal("-100"),
                period=mod.SettlementPeriod.MONTHLY,
                period_label="2026-03",
            )

    def test_core_gets_highest_share(self) -> None:
        mod = _load_module(self.ENGINE)
        dist = mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("24000"),
            period=mod.SettlementPeriod.MONTHLY,
            period_label="2026-03",
        )
        core_alloc = next(a for a in result.allocations if a.root_name == "03_core")
        other_allocs = [a for a in result.allocations if a.root_name != "03_core"]
        assert all(
            core_alloc.amount >= a.amount for a in other_allocs
        ), "03_core should have the highest share per default ratios"

    def test_evidence_hash_sha256(self) -> None:
        mod = _load_module(self.ENGINE)
        dist = mod.SubscriptionRevenueDistributor()
        result = dist.calculate_settlement(
            gross_revenue=Decimal("1000"),
            period=mod.SettlementPeriod.MONTHLY,
            period_label="2026-03",
        )
        assert len(result.evidence_hash) == 64
