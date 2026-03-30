"""Tests for Fee Distribution Engine — Phase 4."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decimal import Decimal
from fee_distribution_engine import FeeDistributionEngine


def test_basic_fee_calculation():
    engine = FeeDistributionEngine(circulating_supply=Decimal("1000000000"))
    alloc = engine.calculate_fee(Decimal("100"))

    assert alloc.total_fee == Decimal("3.00000000")  # 3%
    assert alloc.dev_reward == Decimal("1.00000000")  # 1%
    assert alloc.treasury_share == Decimal("2.00000000")  # 2%
    assert alloc.burn_amount == Decimal("1.00000000")  # 50% of treasury
    assert alloc.treasury_net == Decimal("1.00000000")
    print("PASS: test_basic_fee_calculation")


def test_fee_invariants():
    engine = FeeDistributionEngine(circulating_supply=Decimal("1000000000"))
    for amount in [Decimal("1"), Decimal("100"), Decimal("999999")]:
        engine.calculate_fee(amount)
    result = engine.invariant_check()
    assert result["invariant"] == "PASS"
    assert result["transactions_checked"] == 3
    print("PASS: test_fee_invariants")


def test_daily_burn_cap():
    supply = Decimal("1000")
    engine = FeeDistributionEngine(circulating_supply=supply)
    # Daily cap = 0.5% of 1000 = 5
    # Each tx of 1000 would burn 10 (50% of 20), but capped
    engine.calculate_fee(Decimal("1000"))
    assert engine.daily_burned <= supply * Decimal("0.005")
    print("PASS: test_daily_burn_cap")


def test_evidence_hash():
    engine = FeeDistributionEngine(circulating_supply=Decimal("1000000000"))
    alloc = engine.calculate_fee(Decimal("50"))
    h = alloc.evidence_hash()
    assert len(h) == 64  # SHA-256 hex
    print("PASS: test_evidence_hash")


def test_zero_amount_rejected():
    engine = FeeDistributionEngine(circulating_supply=Decimal("1000000000"))
    try:
        engine.calculate_fee(Decimal("0"))
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("PASS: test_zero_amount_rejected")


if __name__ == "__main__":
    test_basic_fee_calculation()
    test_fee_invariants()
    test_daily_burn_cap()
    test_evidence_hash()
    test_zero_amount_rejected()
    print("\nALL TESTS PASSED")
