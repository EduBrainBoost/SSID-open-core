# SSID Brain Control -- Core approval and feedback components
"""Brain Control: Approval Gate, Feedback Collector."""

from .approval_gate import ApprovalGate, GateDecision, GateResult
from .feedback_collector import FeedbackCollector

__all__ = [
    "ApprovalGate",
    "GateResult",
    "GateDecision",
    "FeedbackCollector",
]
__version__ = "0.1.0"
