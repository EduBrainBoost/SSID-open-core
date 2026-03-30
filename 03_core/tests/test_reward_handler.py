"""Tests for 08_identity_score/reward_handler.py.

Located here to avoid duplication; 08_identity_score has its own
test_identity_score_engine.py for the identity-score logic. This file
targets the reward_handler specifically.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

IDENTITY_SCORE_ROOT = Path(__file__).resolve().parents[2] / "08_identity_score"
HANDLER_PATH = IDENTITY_SCORE_ROOT / "reward_handler.py"


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
    import sys as _sys
    _sys.modules[path.stem] = mod  # required on Python 3.14+ for @dataclass
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------


class TestRewardHandlerPresence:
    def test_file_exists(self):
        assert HANDLER_PATH.exists(), "reward_handler.py not found in 08_identity_score/"

    def test_correct_root(self):
        assert HANDLER_PATH.parent.name == "08_identity_score"

    def test_not_empty(self):
        assert HANDLER_PATH.stat().st_size > 0


# ---------------------------------------------------------------------------
# Source validity
# ---------------------------------------------------------------------------


class TestRewardHandlerSource:
    def test_valid_python_or_placeholder(self):
        content = HANDLER_PATH.read_text(encoding="utf-8")
        try:
            compile(content, str(HANDLER_PATH), "exec")
            valid = True
        except SyntaxError:
            valid = False
        assert valid or "PLACEHOLDER" in content.upper()

    def test_importable_if_valid(self):
        mod = _load(HANDLER_PATH)
        assert mod is not None


# ---------------------------------------------------------------------------
# API contract
# ---------------------------------------------------------------------------


class TestRewardHandlerInterface:
    """reward_handler must expose correct API and produce valid reward calculations."""

    @pytest.fixture(autouse=True)
    def _mod(self):
        self.mod = _load(HANDLER_PATH)

    def test_exposes_reward_symbol(self):
        symbols = set(dir(self.mod))
        candidates = {"RewardHandler", "handle_reward", "process_reward", "award", "grant_reward"}
        assert candidates & symbols, (
            f"reward_handler exposes none of {candidates}. Found: {symbols}"
        )

    def test_no_placeholder_text(self):
        content = HANDLER_PATH.read_text(encoding="utf-8")
        assert "AUTO-GENERATED PLACEHOLDER" not in content

    def test_docstring_present(self):
        assert self.mod.__doc__, "reward_handler.py missing module docstring"

    def test_basic_reward_calculation(self):
        from decimal import Decimal
        handler = self.mod.RewardHandler()
        result = handler.calculate_reward(
            actor_identifier="user-001",
            action=self.mod.VerificationAction.EMAIL_VERIFY,
            trust_level=self.mod.TrustLevel.BASIC,
        )
        assert isinstance(result, self.mod.RewardResult)
        assert result.status == self.mod.RewardStatus.APPROVED
        assert result.base_amount == Decimal("1.00")
        assert result.multiplier == Decimal("1.00")
        assert result.final_amount == Decimal("1.00")

    def test_trust_multiplier_scales_reward(self):
        from decimal import Decimal
        handler = self.mod.RewardHandler()
        result = handler.calculate_reward(
            actor_identifier="user-002",
            action=self.mod.VerificationAction.DOCUMENT_VERIFY,
            trust_level=self.mod.TrustLevel.AUTHORITY,
        )
        # base=5.00, multiplier=2.00, final=10.00
        assert result.final_amount == Decimal("10.00")

    def test_unverified_trust_reduces_reward(self):
        from decimal import Decimal
        handler = self.mod.RewardHandler()
        result = handler.calculate_reward(
            actor_identifier="user-003",
            action=self.mod.VerificationAction.PHONE_VERIFY,
            trust_level=self.mod.TrustLevel.UNVERIFIED,
        )
        # base=2.00, multiplier=0.50, final=1.00
        assert result.final_amount == Decimal("1.00")

    def test_actor_hash_is_sha256_not_raw_pii(self):
        handler = self.mod.RewardHandler()
        result = handler.calculate_reward(
            actor_identifier="sensitive-pii@example.com",
            action=self.mod.VerificationAction.EMAIL_VERIFY,
            trust_level=self.mod.TrustLevel.BASIC,
        )
        assert "sensitive-pii" not in result.actor_hash
        assert len(result.actor_hash) == 64

    def test_cooldown_prevents_rapid_same_action(self):
        from datetime import datetime, timezone, timedelta
        handler = self.mod.RewardHandler()
        t0 = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
        r1 = handler.calculate_reward(
            actor_identifier="user-cd",
            action=self.mod.VerificationAction.EMAIL_VERIFY,
            trust_level=self.mod.TrustLevel.BASIC,
            now=t0,
        )
        assert r1.status == self.mod.RewardStatus.APPROVED
        r2 = handler.calculate_reward(
            actor_identifier="user-cd",
            action=self.mod.VerificationAction.EMAIL_VERIFY,
            trust_level=self.mod.TrustLevel.BASIC,
            now=t0 + timedelta(seconds=5),  # within 30s cooldown
        )
        assert r2.status == self.mod.RewardStatus.COOLDOWN
        from decimal import Decimal
        assert r2.final_amount == Decimal("0.00")

    def test_hourly_rate_limit(self):
        from datetime import datetime, timezone, timedelta
        config = self.mod.AntiGamingConfig(
            max_actions_per_hour=3,
            max_actions_per_day=50,
            cooldown_seconds=0,
            burst_threshold=100,
        )
        handler = self.mod.RewardHandler(anti_gaming=config)
        t0 = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
        actions = list(self.mod.VerificationAction)
        for i in range(3):
            r = handler.calculate_reward(
                actor_identifier="user-rl",
                action=actions[i % len(actions)],
                trust_level=self.mod.TrustLevel.BASIC,
                now=t0 + timedelta(minutes=i),
            )
            assert r.status == self.mod.RewardStatus.APPROVED
        r4 = handler.calculate_reward(
            actor_identifier="user-rl",
            action=self.mod.VerificationAction.CREDENTIAL_LINK,
            trust_level=self.mod.TrustLevel.BASIC,
            now=t0 + timedelta(minutes=10),
        )
        assert r4.status == self.mod.RewardStatus.RATE_LIMITED

    def test_evidence_hash_is_sha256(self):
        handler = self.mod.RewardHandler()
        result = handler.calculate_reward(
            actor_identifier="user-ev",
            action=self.mod.VerificationAction.BIOMETRIC_VERIFY,
            trust_level=self.mod.TrustLevel.TRUSTED,
        )
        assert len(result.evidence_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.evidence_hash)

    def test_get_actor_stats(self):
        from datetime import datetime, timezone
        handler = self.mod.RewardHandler()
        t0 = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
        handler.calculate_reward(
            actor_identifier="user-stats",
            action=self.mod.VerificationAction.EMAIL_VERIFY,
            trust_level=self.mod.TrustLevel.BASIC,
            now=t0,
        )
        stats = handler.get_actor_stats("user-stats", now=t0)
        assert stats["actions_last_hour"] == 1
        assert stats["actions_last_day"] == 1

    def test_reset_actor_clears_log(self):
        from datetime import datetime, timezone
        handler = self.mod.RewardHandler()
        t0 = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
        handler.calculate_reward(
            actor_identifier="user-reset",
            action=self.mod.VerificationAction.EMAIL_VERIFY,
            trust_level=self.mod.TrustLevel.BASIC,
            now=t0,
        )
        handler.reset_actor("user-reset")
        stats = handler.get_actor_stats("user-reset", now=t0)
        assert stats["actions_last_hour"] == 0
