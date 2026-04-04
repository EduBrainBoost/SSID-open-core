#!/usr/bin/env python3
"""Unit tests for fairness_engine.py.

Covers demographic parity, equal opportunity, disparate impact,
verdict logic, and hash-only evidence generation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fairness_engine import (
    FairnessEngine,
    FairnessMetric,
    FairnessReport,
    FairnessVerdict,
    GroupOutcome,
)

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def engine() -> FairnessEngine:
    return FairnessEngine()


@pytest.fixture
def fair_groups() -> list:
    """Two groups with nearly identical positive rates."""
    return [
        GroupOutcome(group_id="group_a_hash", total=100, positive=80, negative=20),
        GroupOutcome(group_id="group_b_hash", total=100, positive=78, negative=22),
    ]


@pytest.fixture
def unfair_groups() -> list:
    """Two groups with a large gap in positive rates."""
    return [
        GroupOutcome(group_id="group_a_hash", total=100, positive=90, negative=10),
        GroupOutcome(group_id="group_b_hash", total=100, positive=50, negative=50),
    ]


# -----------------------------------------------------------------------
# GroupOutcome tests
# -----------------------------------------------------------------------


class TestGroupOutcome:
    def test_positive_rate(self) -> None:
        g = GroupOutcome("h", total=200, positive=100, negative=100)
        assert g.positive_rate == 0.5

    def test_positive_rate_zero_total(self) -> None:
        g = GroupOutcome("h", total=0, positive=0, negative=0)
        assert g.positive_rate == 0.0


# -----------------------------------------------------------------------
# Fair scenario
# -----------------------------------------------------------------------


class TestFairScenario:
    def test_all_metrics_pass(self, engine: FairnessEngine, fair_groups: list) -> None:
        report = engine.evaluate("model_abc", fair_groups)
        assert report.verdict == FairnessVerdict.PASS
        assert all(m.passed for m in report.metric_results)

    def test_demographic_parity_value(self, engine: FairnessEngine, fair_groups: list) -> None:
        report = engine.evaluate(
            "model_abc",
            fair_groups,
            metrics=[FairnessMetric.DEMOGRAPHIC_PARITY],
        )
        dp = report.metric_results[0]
        assert dp.metric == FairnessMetric.DEMOGRAPHIC_PARITY
        assert dp.value == pytest.approx(0.02, abs=0.001)
        assert dp.passed is True

    def test_disparate_impact_above_threshold(self, engine: FairnessEngine, fair_groups: list) -> None:
        report = engine.evaluate(
            "model_abc",
            fair_groups,
            metrics=[FairnessMetric.DISPARATE_IMPACT],
        )
        di = report.metric_results[0]
        assert di.value >= 0.80
        assert di.passed is True


# -----------------------------------------------------------------------
# Unfair scenario
# -----------------------------------------------------------------------


class TestUnfairScenario:
    def test_verdict_fail(self, engine: FairnessEngine, unfair_groups: list) -> None:
        report = engine.evaluate("biased_model", unfair_groups)
        assert report.verdict in (FairnessVerdict.FAIL, FairnessVerdict.WARN)

    def test_demographic_parity_fails(self, engine: FairnessEngine, unfair_groups: list) -> None:
        report = engine.evaluate(
            "biased_model",
            unfair_groups,
            metrics=[FairnessMetric.DEMOGRAPHIC_PARITY],
        )
        dp = report.metric_results[0]
        assert dp.passed is False
        # 0.9 - 0.5 = 0.4 >> 0.10 threshold
        assert dp.value == pytest.approx(0.4, abs=0.01)

    def test_disparate_impact_fails(self, engine: FairnessEngine, unfair_groups: list) -> None:
        report = engine.evaluate(
            "biased_model",
            unfair_groups,
            metrics=[FairnessMetric.DISPARATE_IMPACT],
        )
        di = report.metric_results[0]
        assert di.passed is False
        # 0.5/0.9 ~ 0.556, below 0.80
        assert di.value < 0.80


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------


class TestEdgeCases:
    def test_fewer_than_2_groups_raises(self, engine: FairnessEngine) -> None:
        with pytest.raises(ValueError, match="At least 2 groups"):
            engine.evaluate("m", [GroupOutcome("a", 10, 5, 5)])

    def test_three_groups(self, engine: FairnessEngine) -> None:
        groups = [
            GroupOutcome("a", 100, 80, 20),
            GroupOutcome("b", 100, 75, 25),
            GroupOutcome("c", 100, 70, 30),
        ]
        report = engine.evaluate("m3", groups)
        assert isinstance(report, FairnessReport)

    def test_custom_thresholds(self) -> None:
        strict_engine = FairnessEngine(thresholds={FairnessMetric.DEMOGRAPHIC_PARITY: 0.01})
        groups = [
            GroupOutcome("a", 100, 80, 20),
            GroupOutcome("b", 100, 78, 22),
        ]
        report = strict_engine.evaluate("strict", groups, metrics=[FairnessMetric.DEMOGRAPHIC_PARITY])
        assert report.metric_results[0].passed is False  # 0.02 > 0.01


# -----------------------------------------------------------------------
# Evidence
# -----------------------------------------------------------------------


class TestEvidence:
    def test_evidence_hash_sha256(self, engine: FairnessEngine, fair_groups: list) -> None:
        report = engine.evaluate("m", fair_groups)
        assert len(report.evidence_hash) == 64

    def test_report_id_present(self, engine: FairnessEngine, fair_groups: list) -> None:
        report = engine.evaluate("m", fair_groups)
        assert len(report.report_id) == 16

    def test_model_id_preserved(self, engine: FairnessEngine, fair_groups: list) -> None:
        report = engine.evaluate("my_model_hash", fair_groups)
        assert report.model_id == "my_model_hash"


# -----------------------------------------------------------------------
# Verdict logic
# -----------------------------------------------------------------------


class TestVerdictLogic:
    def test_disparate_impact_fail_forces_fail(self) -> None:
        """If disparate impact fails, overall verdict must be FAIL."""
        engine = FairnessEngine(
            thresholds={
                FairnessMetric.DEMOGRAPHIC_PARITY: 1.0,  # very lenient
                FairnessMetric.EQUAL_OPPORTUNITY: 1.0,
                FairnessMetric.DISPARATE_IMPACT: 0.99,  # very strict
            }
        )
        groups = [
            GroupOutcome("a", 100, 90, 10),
            GroupOutcome("b", 100, 80, 20),
        ]
        report = engine.evaluate("m", groups)
        assert report.verdict == FairnessVerdict.FAIL

    def test_single_non_di_failure_is_warn(self) -> None:
        """A single non-DI metric failure should produce WARN, not FAIL."""
        engine = FairnessEngine(
            thresholds={
                FairnessMetric.DEMOGRAPHIC_PARITY: 0.001,  # strict
                FairnessMetric.EQUAL_OPPORTUNITY: 1.0,  # lenient
                FairnessMetric.DISPARATE_IMPACT: 0.01,  # lenient
            }
        )
        groups = [
            GroupOutcome("a", 100, 80, 20),
            GroupOutcome("b", 100, 79, 21),
        ]
        report = engine.evaluate("m", groups)
        # DP fails (0.01 > 0.001), but DI passes (79/80 ~ 0.9875 > 0.01)
        assert report.verdict == FairnessVerdict.WARN
