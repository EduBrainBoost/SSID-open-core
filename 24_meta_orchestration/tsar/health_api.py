"""TSAR Health API - Endpoint-ready functions for system health monitoring."""

from .tsar_engine import (
    IssueSeverity,
    IssueType,
    TSAREngine,
)


class HealthAPI:
    """API layer for TSAR health queries and remediation queue management."""

    def __init__(self, engine: TSAREngine | None = None):
        self.engine = engine or TSAREngine()

    def get_health(self) -> dict:
        """Return current system health summary."""
        return self.engine.get_health_status()

    def get_issues(
        self,
        severity: IssueSeverity | None = None,
        issue_type: IssueType | None = None,
        resolved: bool | None = None,
    ) -> list[dict]:
        """Return filtered list of detected issues."""
        filtered = self.engine.issues
        if severity is not None:
            filtered = [i for i in filtered if i.severity == severity]
        if issue_type is not None:
            filtered = [i for i in filtered if i.issue_type == issue_type]
        if resolved is not None:
            filtered = [i for i in filtered if i.resolved == resolved]
        return [
            {
                "issue_id": i.issue_id,
                "issue_type": i.issue_type.value,
                "severity": i.severity.value,
                "description": i.description,
                "affected_path": i.affected_path,
                "detected_at": i.detected_at,
                "remediation": i.remediation.value,
                "resolved": i.resolved,
            }
            for i in filtered
        ]

    def get_remediation_queue(self) -> list[dict]:
        """Return issues pending remediation, ordered by severity."""
        severity_order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3,
        }
        pending = [i for i in self.engine.issues if not i.resolved]
        pending.sort(key=lambda i: severity_order.get(i.severity, 99))
        return [
            {
                "issue_id": i.issue_id,
                "issue_type": i.issue_type.value,
                "severity": i.severity.value,
                "description": i.description,
                "remediation": i.remediation.value,
                "auto_fix_allowed": self.engine.guardrails.is_auto_fix_allowed(i),
            }
            for i in pending
        ]
