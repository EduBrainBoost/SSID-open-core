"""
SSID Fee Distribution Engine
Root: 03_core | Shard: 10_finanzen_banking
Source: SSID_structure_gebuehren_abo_modelle.md (Tier-0 SoT)

Implements the canonical 3% fee model:
- 1% developer reward (direct)
- 2% system treasury
- 50% of treasury share burned (with daily/monthly caps)

Non-custodial: All fee routing via smart contract logic.
No manual intervention.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional


@dataclass
class FeeAllocation:
    """Result of a fee distribution calculation."""
    transaction_amount: Decimal
    total_fee: Decimal
    dev_reward: Decimal
    treasury_share: Decimal
    burn_amount: Decimal
    treasury_net: Decimal
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "transaction_amount": str(self.transaction_amount),
            "total_fee": str(self.total_fee),
            "dev_reward": str(self.dev_reward),
            "treasury_share": str(self.treasury_share),
            "burn_amount": str(self.burn_amount),
            "treasury_net": str(self.treasury_net),
            "timestamp_utc": self.timestamp_utc,
        }

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode()
        ).hexdigest()


class FeeDistributionEngine:
    """Canonical SSID fee distribution per Tier-0 SoT."""

    TOTAL_FEE_RATE = Decimal("0.03")       # 3%
    DEV_FEE_RATE = Decimal("0.01")         # 1% of transaction
    TREASURY_FEE_RATE = Decimal("0.02")    # 2% of transaction
    BURN_RATE = Decimal("0.50")            # 50% of treasury share
    DAILY_BURN_CAP_RATE = Decimal("0.005") # 0.5% of circulating supply
    MONTHLY_BURN_CAP_RATE = Decimal("0.02") # 2% of circulating supply

    def __init__(self, circulating_supply: Decimal):
        self.circulating_supply = circulating_supply
        self.daily_burned = Decimal("0")
        self.monthly_burned = Decimal("0")
        self.total_burned = Decimal("0")
        self.total_dev_rewards = Decimal("0")
        self.total_treasury = Decimal("0")
        self._ledger: list[FeeAllocation] = []

    def calculate_fee(self, transaction_amount: Decimal) -> FeeAllocation:
        """Calculate fee distribution for a verification transaction."""
        if transaction_amount <= 0:
            raise ValueError("Transaction amount must be positive")

        total_fee = (transaction_amount * self.TOTAL_FEE_RATE).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        dev_reward = (transaction_amount * self.DEV_FEE_RATE).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        treasury_share = total_fee - dev_reward

        # Calculate burn with caps
        raw_burn = (treasury_share * self.BURN_RATE).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        daily_cap = self.circulating_supply * self.DAILY_BURN_CAP_RATE
        monthly_cap = self.circulating_supply * self.MONTHLY_BURN_CAP_RATE

        burn_amount = min(
            raw_burn,
            daily_cap - self.daily_burned,
            monthly_cap - self.monthly_burned,
        )
        burn_amount = max(burn_amount, Decimal("0"))

        treasury_net = treasury_share - burn_amount

        allocation = FeeAllocation(
            transaction_amount=transaction_amount,
            total_fee=total_fee,
            dev_reward=dev_reward,
            treasury_share=treasury_share,
            burn_amount=burn_amount,
            treasury_net=treasury_net,
        )

        self._apply(allocation)
        return allocation

    def _apply(self, allocation: FeeAllocation) -> None:
        self.daily_burned += allocation.burn_amount
        self.monthly_burned += allocation.burn_amount
        self.total_burned += allocation.burn_amount
        self.total_dev_rewards += allocation.dev_reward
        self.total_treasury += allocation.treasury_net
        self._ledger.append(allocation)

    def reset_daily(self) -> None:
        self.daily_burned = Decimal("0")

    def reset_monthly(self) -> None:
        self.monthly_burned = Decimal("0")

    @property
    def ledger_count(self) -> int:
        return len(self._ledger)

    def invariant_check(self) -> dict:
        """Verify mathematical invariants hold."""
        for alloc in self._ledger:
            expected_total = alloc.dev_reward + alloc.treasury_share
            fee_match = alloc.total_fee == expected_total
            treasury_match = alloc.treasury_net == alloc.treasury_share - alloc.burn_amount
            if not fee_match or not treasury_match:
                return {"invariant": "FAIL", "allocation": alloc.to_dict()}
        return {"invariant": "PASS", "transactions_checked": len(self._ledger)}
