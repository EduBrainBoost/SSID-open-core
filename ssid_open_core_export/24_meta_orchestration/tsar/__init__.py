"""TSAR - Trustworthy Self-Adaptive Repair.

Provides self-healing capabilities for the SSID system:
- Structural drift detection (ROOT-24-LOCK compliance)
- Evidence chain verification
- Registry consistency checks
- Safe remediation with guardrails
"""

from .health_api import HealthAPI
from .issue_detector import CANONICAL_ROOTS, IssueDetector
from .tsar_engine import (
    DetectedIssue,
    IssueSeverity,
    IssueType,
    RemediationAction,
    TSAREngine,
    TSARGuardrails,
)

__all__ = [
    "TSAREngine",
    "TSARGuardrails",
    "DetectedIssue",
    "IssueType",
    "IssueSeverity",
    "RemediationAction",
    "HealthAPI",
    "IssueDetector",
    "CANONICAL_ROOTS",
]
