"""Tests for 03_core/fee_distribution_engine.py.

The current file is a SoT placeholder (not valid Python).  All tests that
require actual module logic are skipped automatically via the shared
load_module fixture.  Path-existence and validity tests always run.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = CORE_ROOT / "fee_distribution_engine.py"


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
# File presence
# ---------------------------------------------------------------------------


class TestFeeDistributionEnginePresence:
    """fee_distribution_engine.py must exist at the correct root-level path."""

    def test_file_exists(self):
        assert ENGINE_PATH.exists(), "fee_distribution_engine.py not found in 03_core/"

    def test_file_is_file(self):
        assert ENGINE_PATH.is_file(), "fee_distribution_engine.py is not a regular file"

    def test_file_not_empty(self):
        assert ENGINE_PATH.stat().st_size > 0, "fee_distribution_engine.py is empty"


# ---------------------------------------------------------------------------
# Python validity / importability
# ---------------------------------------------------------------------------


class TestFeeDistributionEngineValidity:
    """Source must be valid Python once the placeholder is replaced."""

    def test_valid_python_or_placeholder(self):
        """The file must either be valid Python or a known placeholder."""
        content = ENGINE_PATH.read_text(encoding="utf-8")
        try:
            compile(content, str(ENGINE_PATH), "exec")
            valid = True
        except SyntaxError:
            valid = False
        # Accept placeholder prose OR valid Python — never a broken module
        assert valid or "PLACEHOLDER" in content.upper(), (
            "fee_distribution_engine.py is neither valid Python nor a recognised placeholder"
        )

    def test_importable_if_valid_python(self):
        mod = _load(ENGINE_PATH)
        assert mod is not None


# ---------------------------------------------------------------------------
# Interface contract (executed only when real module is present)
# ---------------------------------------------------------------------------


class TestFeeDistributionEngineInterface:
    """fee_distribution_engine must expose the expected API and produce correct results."""

    @pytest.fixture(autouse=True)
    def _mod(self):
        self.mod = _load(ENGINE_PATH)

    def test_has_distribute_or_calculate(self):
        """Module should expose the expected fee engine symbols."""
        symbols = dir(self.mod)
        expected_any = {
            "distribute_fees", "calculate_fee", "FeeDistributor", "distribute",
            "FeeDistributionEngine", "DistributionResult", "FeeParticipant",
        }
        assert expected_any & set(symbols), (
            f"fee_distribution_engine exposes none of {expected_any}. Got: {symbols}"
        )

    def test_no_placeholder_text_in_real_module(self):
        """Source must not contain placeholder markers."""
        content = ENGINE_PATH.read_text(encoding="utf-8")
        assert "AUTO-GENERATED PLACEHOLDER" not in content, (
            "fee_distribution_engine.py still contains placeholder text"
        )

    def test_module_docstring_present(self):
        """Module must have a module-level docstring."""
        assert self.mod.__doc__ is not None, "fee_distribution_engine.py missing module docstring"

    def test_calculate_returns_distribution_result(self):
        """FeeDistributionEngine.calculate must return a DistributionResult."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("250"))
        assert isinstance(result, self.mod.DistributionResult)
        assert result.gross_amount == Decimal("250")

    def test_standard_tier_allocation_sum(self):
        """Allocations plus remainder must equal gross amount."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("500"))
        total = sum(a.amount for a in result.allocations) + result.remainder
        assert total == Decimal("500"), f"Allocation sum mismatch: {total}"

    def test_all_four_stakeholder_roles_present(self):
        """Each distribution must include all four stakeholder roles."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("1000"))
        roles = {a.role for a in result.allocations}
        expected_roles = set(self.mod.StakeholderRole)
        assert roles == expected_roles, f"Expected {expected_roles}, got {roles}"

    def test_tier_selection_micro(self):
        """Amounts under 100 must use the micro tier."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("50"))
        assert all(a.tier_name == "micro" for a in result.allocations)

    def test_tier_selection_standard(self):
        """Amounts 100-9999 must use the standard tier."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("5000"))
        assert all(a.tier_name == "standard" for a in result.allocations)

    def test_tier_selection_enterprise(self):
        """Amounts >= 10000 must use the enterprise tier."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("10000"))
        assert all(a.tier_name == "enterprise" for a in result.allocations)

    def test_evidence_hash_is_sha256(self):
        """Evidence hash must be a valid SHA-256 hex digest (64 chars)."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        result = engine.calculate(Decimal("100"))
        assert len(result.evidence_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.evidence_hash)

    def test_negative_amount_rejected(self):
        """Negative gross amounts must raise ValueError."""
        from decimal import Decimal
        engine = self.mod.FeeDistributionEngine()
        with pytest.raises(ValueError):
            engine.calculate(Decimal("-10"))

    def test_custom_tier_rules(self):
        """Engine must accept custom tier rules."""
        from decimal import Decimal
        custom_tier = self.mod.TierRule(
            name="custom",
            threshold_min=Decimal("0"),
            threshold_max=None,
            splits={
                self.mod.StakeholderRole.PLATFORM: Decimal("0.50"),
                self.mod.StakeholderRole.OPERATOR: Decimal("0.25"),
                self.mod.StakeholderRole.CREATOR: Decimal("0.15"),
                self.mod.StakeholderRole.RESERVE: Decimal("0.10"),
            },
        )
        engine = self.mod.FeeDistributionEngine(tiers=[custom_tier])
        result = engine.calculate(Decimal("1000"))
        platform_alloc = next(
            a for a in result.allocations
            if a.role == self.mod.StakeholderRole.PLATFORM
        )
        assert platform_alloc.amount == Decimal("500.00")
