#!/usr/bin/env python3
"""Fee Distribution CLI Calculator.

Computes the SSID fee distribution for a given transaction amount.
Fee model: total=3%, developer_share=1%, system_pool=2%.
The system pool is split across 7 pillars (equal share).

Non-custodial: produces JSON output only, no funds are moved.
Uses Decimal for precision. No PII stored.

SoT v4.1.0 | ROOT-24-LOCK | Module: 12_tooling
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# ---------------------------------------------------------------------------
# Fee constants (immutable)
# ---------------------------------------------------------------------------
TOTAL_FEE_RATE = Decimal("0.03")        # 3%
DEVELOPER_RATE = Decimal("0.01")        # 1%
SYSTEM_POOL_RATE = Decimal("0.02")      # 2%

SEVEN_PILLARS = [
    "infrastructure",
    "security",
    "governance",
    "community",
    "research",
    "compliance",
    "reserve",
]

PILLAR_COUNT = Decimal(str(len(SEVEN_PILLARS)))
TWO_PLACES = Decimal("0.01")


def calculate_fee(amount: Decimal) -> dict:
    """Calculate fee distribution for *amount*.

    Args:
        amount: Transaction amount (must be >= 0).

    Returns:
        dict with all fee components as string-encoded Decimals.

    Raises:
        ValueError: If amount is negative.
    """
    if amount < Decimal("0"):
        raise ValueError("Amount must be non-negative")

    total_fee = (amount * TOTAL_FEE_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    developer_share = (amount * DEVELOPER_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    system_pool = (amount * SYSTEM_POOL_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Split system pool across 7 pillars with remainder handling
    pillar_base = (system_pool / PILLAR_COUNT).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    pillars: dict[str, str] = {}
    allocated = Decimal("0")

    for i, name in enumerate(SEVEN_PILLARS):
        if i < len(SEVEN_PILLARS) - 1:
            pillars[name] = str(pillar_base)
            allocated += pillar_base
        else:
            # Last pillar absorbs rounding remainder
            last = system_pool - allocated
            pillars[name] = str(last)
            allocated += last

    return {
        "amount": str(amount),
        "total_fee_rate": str(TOTAL_FEE_RATE),
        "total_fee": str(total_fee),
        "developer_share_rate": str(DEVELOPER_RATE),
        "developer_share": str(developer_share),
        "system_pool_rate": str(SYSTEM_POOL_RATE),
        "system_pool": str(system_pool),
        "pillars": pillars,
        "pillar_sum": str(allocated),
        "sum_check": str(developer_share + allocated),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SSID Fee Distribution Calculator (3%% total: 1%% dev, 2%% system/7-pillars)",
    )
    parser.add_argument(
        "amount",
        type=str,
        help="Transaction amount (decimal number, >= 0)",
    )
    args = parser.parse_args(argv)

    try:
        amount = Decimal(args.amount)
    except InvalidOperation:
        print(json.dumps({"error": f"Invalid amount: {args.amount}"}), file=sys.stderr)
        return 1

    try:
        result = calculate_fee(amount)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
