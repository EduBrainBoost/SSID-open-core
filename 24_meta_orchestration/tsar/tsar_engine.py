"""TSAR - Trustworthy Self-Adaptive Repair Engine.
Detects structural/policy/runtime anomalies and triggers safe remediation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import json
import hashlib


class IssueType(Enum):
    STRUCTURE_DRIFT = "structure_drift"
    POLICY_VIOLATION = "policy_violation"
    RUNTIME_ANOMALY = "runtime_anomaly"
    EVIDENCE_GAP = "evidence_gap"
    REGISTRY_INCONSISTENCY = "registry_inconsistency"


class IssueSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemediationAction(Enum):
    AUTO_FIX = "auto_fix"
    ALERT_ONLY = "alert_only"
    QUARANTINE = "quarantine"
    APPROVAL_REQUIRED = "approval_required"


@dataclass
class DetectedIssue:
    issue_id: str
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    affected_path: str
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    remediation: RemediationAction = RemediationAction.ALERT_ONLY
    resolved: bool = False


class TSAREngine:
    """Core TSAR engine for issue detection and safe remediation."""

    def __init__(self):
        self.issues: List[DetectedIssue] = []
        self.guardrails = TSARGuardrails()

    def detect_structure_drift(
        self, expected_roots: List[str], actual_roots: List[str]
    ) -> List[DetectedIssue]:
        """Detect deviations from ROOT-24-LOCK."""
        issues = []
        for root in expected_roots:
            if root not in actual_roots:
                issues.append(
                    DetectedIssue(
                        issue_id=f"TSAR-{len(self.issues)+len(issues)+1:04d}",
                        issue_type=IssueType.STRUCTURE_DRIFT,
                        severity=IssueSeverity.CRITICAL,
                        description=f"Expected root '{root}' missing",
                        affected_path=root,
                        remediation=RemediationAction.APPROVAL_REQUIRED,
                    )
                )
        for root in actual_roots:
            if root not in expected_roots:
                issues.append(
                    DetectedIssue(
                        issue_id=f"TSAR-{len(self.issues)+len(issues)+1:04d}",
                        issue_type=IssueType.STRUCTURE_DRIFT,
                        severity=IssueSeverity.HIGH,
                        description=f"Unexpected root '{root}' found",
                        affected_path=root,
                        remediation=RemediationAction.ALERT_ONLY,
                    )
                )
        self.issues.extend(issues)
        return issues

    def detect_evidence_gaps(
        self, required_evidence: List[str], existing_evidence: List[str]
    ) -> List[DetectedIssue]:
        """Detect missing evidence entries."""
        issues = []
        for ev in required_evidence:
            if ev not in existing_evidence:
                issues.append(
                    DetectedIssue(
                        issue_id=f"TSAR-{len(self.issues)+len(issues)+1:04d}",
                        issue_type=IssueType.EVIDENCE_GAP,
                        severity=IssueSeverity.MEDIUM,
                        description=f"Evidence missing: {ev}",
                        affected_path=ev,
                        remediation=RemediationAction.AUTO_FIX,
                    )
                )
        self.issues.extend(issues)
        return issues

    def resolve_issue(self, issue_id: str) -> bool:
        """Mark an issue as resolved."""
        for issue in self.issues:
            if issue.issue_id == issue_id:
                issue.resolved = True
                return True
        return False

    def get_health_status(self) -> dict:
        """Return current system health status."""
        critical = sum(
            1
            for i in self.issues
            if i.severity == IssueSeverity.CRITICAL and not i.resolved
        )
        high = sum(
            1
            for i in self.issues
            if i.severity == IssueSeverity.HIGH and not i.resolved
        )
        if critical > 0:
            status = "CRITICAL"
        elif high > 0:
            status = "DEGRADED"
        else:
            status = "HEALTHY"
        return {
            "status": status,
            "total_issues": len(self.issues),
            "unresolved_critical": critical,
            "unresolved_high": high,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class TSARGuardrails:
    """Safety guardrails preventing unsafe auto-remediation."""

    NEVER_AUTO_FIX = [IssueType.STRUCTURE_DRIFT]
    MAX_AUTO_FIX_PER_RUN = 10

    def is_auto_fix_allowed(self, issue: DetectedIssue) -> bool:
        """Check if auto-fix is permitted for the given issue."""
        if issue.issue_type in self.NEVER_AUTO_FIX:
            return False
        if issue.remediation == RemediationAction.APPROVAL_REQUIRED:
            return False
        return True
