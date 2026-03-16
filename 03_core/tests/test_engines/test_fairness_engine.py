"""Tests for FairnessEngine.

Covers: Gini coefficient, evaluate_fairness verdicts, detect_bias,
enforce_policy, evidence hashing, edge cases, and determinism.
"""
from __future__ import annotations

import pytest
from fairness_engine import (
    FairnessEngine,
    FairnessError,
)


@pytest.fixture()
def engine() -> FairnessEngine:
    return FairnessEngine()


# ---------------------------------------------------------------------------
# Test 1: Perfect equality yields Gini = 0.0
# ---------------------------------------------------------------------------

def test_gini_perfect_equality(engine: FairnessEngine) -> None:
    values = [10.0, 10.0, 10.0, 10.0]
    gini = engine.gini_coefficient(values)
    assert abs(gini) < 1e-9, f"Expected 0.0, got {gini}"


# ---------------------------------------------------------------------------
# Test 2: Perfect inequality yields Gini close to 1.0
# ---------------------------------------------------------------------------

def test_gini_high_inequality(engine: FairnessEngine) -> None:
    values = [0.0, 0.0, 0.0, 100.0]
    gini = engine.gini_coefficient(values)
    assert gini > 0.7, f"Expected high Gini, got {gini}"


# ---------------------------------------------------------------------------
# Test 3: evaluate_fairness returns 'fair' for equal distribution
# ---------------------------------------------------------------------------

def test_evaluate_fairness_equal_distribution_is_fair(engine: FairnessEngine) -> None:
    distribution = {"a": 100.0, "b": 100.0, "c": 100.0}
    score = engine.evaluate_fairness(distribution)
    assert score.verdict == "fair"
    assert score.gini_coefficient < engine.FAIR_THRESHOLD


# ---------------------------------------------------------------------------
# Test 4: evaluate_fairness returns 'unfair' for skewed distribution
# ---------------------------------------------------------------------------

def test_evaluate_fairness_skewed_distribution_is_unfair(engine: FairnessEngine) -> None:
    distribution = {"whale": 990.0, "p2": 5.0, "p3": 5.0}
    score = engine.evaluate_fairness(distribution)
    assert score.verdict == "unfair"
    assert score.gini_coefficient > engine.MARGINAL_THRESHOLD


# ---------------------------------------------------------------------------
# Test 5: evaluate_fairness criteria tracking
# ---------------------------------------------------------------------------

def test_evaluate_fairness_criteria_tracking(engine: FairnessEngine) -> None:
    distribution = {"a": 50.0, "b": 50.0}
    criteria = {"max_gini": 0.5, "min_share": 0.01}
    score = engine.evaluate_fairness(distribution, criteria)
    assert "max_gini" in score.criteria_met
    assert "min_share" in score.criteria_met
    assert score.criteria_failed == []


# ---------------------------------------------------------------------------
# Test 6: evaluate_fairness evidence hash is deterministic
# ---------------------------------------------------------------------------

def test_evaluate_fairness_deterministic(engine: FairnessEngine) -> None:
    distribution = {"a": 40.0, "b": 60.0}
    s1 = engine.evaluate_fairness(distribution)
    s2 = engine.evaluate_fairness(distribution)
    assert s1.evidence_hash == s2.evidence_hash


# ---------------------------------------------------------------------------
# Test 7: detect_bias identifies attribute with large disparity
# ---------------------------------------------------------------------------

def test_detect_bias_identifies_large_disparity(engine: FairnessEngine) -> None:
    data = [
        {"group": "A", "outcome": 100.0},
        {"group": "A", "outcome": 90.0},
        {"group": "B", "outcome": 10.0},
        {"group": "B", "outcome": 20.0},
    ]
    report = engine.detect_bias(data, protected_attributes=["group"])
    assert "group" in report.biased_attributes
    assert report.verdict in {"potential_bias", "significant_bias"}


# ---------------------------------------------------------------------------
# Test 8: detect_bias returns no_bias for balanced data
# ---------------------------------------------------------------------------

def test_detect_bias_no_bias_balanced_data(engine: FairnessEngine) -> None:
    data = [
        {"group": "X", "outcome": 50.0},
        {"group": "X", "outcome": 50.0},
        {"group": "Y", "outcome": 50.0},
        {"group": "Y", "outcome": 50.0},
    ]
    report = engine.detect_bias(data, protected_attributes=["group"])
    assert report.verdict == "no_bias"
    assert report.biased_attributes == []


# ---------------------------------------------------------------------------
# Test 9: enforce_policy allows compliant action
# ---------------------------------------------------------------------------

def test_enforce_policy_allows_compliant_action(engine: FairnessEngine) -> None:
    action = {"type": "payout", "max_gini": 0.2, "min_share": 0.1}
    constraints = {"max_gini": 0.35, "min_share": 0.05}
    result = engine.enforce_policy(action, constraints)
    assert result.allowed is True
    assert result.constraints_violated == []


# ---------------------------------------------------------------------------
# Test 10: enforce_policy blocks action violating max_gini constraint
# ---------------------------------------------------------------------------

def test_enforce_policy_blocks_violating_action(engine: FairnessEngine) -> None:
    action = {"type": "payout", "max_gini": 0.8, "min_share": 0.01}
    constraints = {"max_gini": 0.35, "min_share": 0.05}
    result = engine.enforce_policy(action, constraints)
    assert result.allowed is False
    assert "max_gini" in result.constraints_violated
    assert "min_share" in result.constraints_violated


# ---------------------------------------------------------------------------
# Test 11: enforce_policy produces valid 64-char evidence hash
# ---------------------------------------------------------------------------

def test_enforce_policy_evidence_hash_length(engine: FairnessEngine) -> None:
    action = {"type": "test_action", "max_gini": 0.1}
    constraints = {"max_gini": 0.5}
    result = engine.enforce_policy(action, constraints)
    assert len(result.evidence_hash) == 64
    assert len(result.input_hash) == 64
