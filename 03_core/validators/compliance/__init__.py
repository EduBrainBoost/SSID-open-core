"""Compliance runtime enforcement validators.

Provides runtime enforcers for:
    - Non-Custodial architecture (GAP-F005)
    - GDPR / DSGVO compliance (GAP-F006)
    - PSD2 boundary enforcement (GAP-F010)
"""

from .gdpr_enforcer import (
    LAWFUL_BASES,
    REQUIRED_SUBJECT_RIGHTS,
    GDPREnforcementResult,
    GDPREnforcer,
    GDPRViolation,
    GDPRViolationType,
)
from .non_custodial_enforcer import (
    EnforcementResult,
    NonCustodialEnforcer,
    Violation,
    ViolationType,
)
from .psd2_boundary_enforcer import (
    VALID_UTILITY_PURPOSES,
    PSD2BoundaryEnforcer,
    PSD2EnforcementResult,
    PSD2Violation,
    PSD2ViolationType,
)

__all__ = [
    # Non-Custodial
    "NonCustodialEnforcer",
    "EnforcementResult",
    "Violation",
    "ViolationType",
    # GDPR
    "GDPREnforcer",
    "GDPREnforcementResult",
    "GDPRViolation",
    "GDPRViolationType",
    "LAWFUL_BASES",
    "REQUIRED_SUBJECT_RIGHTS",
    # PSD2
    "PSD2BoundaryEnforcer",
    "PSD2EnforcementResult",
    "PSD2Violation",
    "PSD2ViolationType",
    "VALID_UTILITY_PURPOSES",
]
