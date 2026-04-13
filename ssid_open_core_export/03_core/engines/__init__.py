"""03_core engines package — Non-custodial compute engines for SSID-open-core.

Exports the four core engine classes for convenient import:

    from engines import FeeDistributionEngine, FairnessEngine
    from engines import SubscriptionRevenueDistributor, RewardHandler
"""

from .fairness_engine import (
    BiasReport,
    FairnessEngine,
    FairnessScore,
    PolicyResult,
)
from .fee_distribution_engine import (
    DistributionMode,
    DistributionResult,
    FeeDistributionEngine,
)
from .reward_handler import (
    Reward,
    RewardBatch,
    RewardHandler,
)
from .subscription_revenue_distributor import (
    PayoutReport,
    RevenueShare,
    SubscriptionRevenueDistributor,
    TieredResult,
    TieredTier,
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
