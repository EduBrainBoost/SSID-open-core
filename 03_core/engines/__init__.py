"""03_core engines package — Non-custodial compute engines for SSID-open-core.

Exports the four core engine classes for convenient import:

    from engines import FeeDistributionEngine, FairnessEngine
    from engines import SubscriptionRevenueDistributor, RewardHandler
"""
from .fee_distribution_engine import (
    FeeDistributionEngine,
    DistributionMode,
    DistributionResult,
)
from .fairness_engine import (
    FairnessEngine,
    FairnessScore,
    BiasReport,
    PolicyResult,
)
from .subscription_revenue_distributor import (
    SubscriptionRevenueDistributor,
    RevenueShare,
    TieredResult,
    TieredTier,
    PayoutReport,
)
from .reward_handler import (
    RewardHandler,
    Reward,
    RewardBatch,
)

__all__ = [
    "FeeDistributionEngine",
    "DistributionMode",
    "DistributionResult",
    "FairnessEngine",
    "FairnessScore",
    "BiasReport",
    "PolicyResult",
    "SubscriptionRevenueDistributor",
    "RevenueShare",
    "TieredResult",
    "TieredTier",
    "PayoutReport",
    "RewardHandler",
    "Reward",
    "RewardBatch",
]
