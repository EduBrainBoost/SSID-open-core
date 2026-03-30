"""
Compliance Dashboard Data Provider (R021)

Aggregates compliance status across all frameworks, computes coverage
percentages, identifies gaps and overdue reviews.

Exports:
    ComplianceDashboardData
    FrameworkStatus
    CoverageReport
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .automated_compliance_monitor import (
    AutomatedComplianceMonitor,
    ComplianceFinding,
    ControlStatus,
    FindingStatus,
    MonitoringResult,
    Severity,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FrameworkStatus:
    """Status summary for a single compliance framework."""

    framework: str
    total_controls: int = 0
    implemented: int = 0
    partial: int = 0
    not_implemented: int = 0
    not_applicable: int = 0
    open_findings: int = 0
    critical_findings: int = 0
    overdue_reviews: int = 0
    last_checked: Optional[str] = None

    @property
    def coverage_percent(self) -> float:
        applicable = self.total_controls - self.not_applicable
        if applicable == 0:
            return 100.0
        return round(
            (self.implemented + self.partial * 0.5) / applicable * 100, 2
        )

    @property
    def full_coverage_percent(self) -> float:
        """Only fully implemented controls count."""
        applicable = self.total_controls - self.not_applicable
        if applicable == 0:
            return 100.0
        return round(self.implemented / applicable * 100, 2)

    @property
    def risk_level(self) -> str:
        if self.critical_findings > 0:
            return "CRITICAL"
        if self.coverage_percent < 50:
            return "HIGH"
        if self.coverage_percent < 80:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "total_controls": self.total_controls,
            "implemented": self.implemented,
            "partial": self.partial,
            "not_implemented": self.not_implemented,
            "not_applicable": self.not_applicable,
            "coverage_percent": self.coverage_percent,
            "full_coverage_percent": self.full_coverage_percent,
            "open_findings": self.open_findings,
            "critical_findings": self.critical_findings,
            "overdue_reviews": self.overdue_reviews,
            "risk_level": self.risk_level,
            "last_checked": self.last_checked,
        }


@dataclass
class CoverageReport:
    """Cross-framework coverage report."""

    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    overall_coverage: float = 0.0
    overall_full_coverage: float = 0.0
    total_controls_all: int = 0
    total_findings: int = 0
    critical_findings: int = 0
    frameworks: list[FrameworkStatus] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    overdue_items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def risk_summary(self) -> str:
        if self.critical_findings > 0:
            return "CRITICAL - Immediate remediation required"
        if self.overall_coverage < 60:
            return "HIGH - Significant coverage gaps"
        if self.overall_coverage < 85:
            return "MEDIUM - Partial coverage, review recommended"
        return "LOW - Adequate coverage"

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overall_coverage": self.overall_coverage,
            "overall_full_coverage": self.overall_full_coverage,
            "total_controls_all": self.total_controls_all,
            "total_findings": self.total_findings,
            "critical_findings": self.critical_findings,
            "risk_summary": self.risk_summary,
            "frameworks": [fw.to_dict() for fw in self.frameworks],
            "gaps": self.gaps,
            "overdue_items": self.overdue_items,
        }


# ---------------------------------------------------------------------------
# Dashboard data aggregator
# ---------------------------------------------------------------------------


class ComplianceDashboardData:
    """
    Aggregates compliance monitoring results into dashboard-ready structures.

    Usage::

        monitor = AutomatedComplianceMonitor(
            frameworks_dir="23_compliance/frameworks",
            evidence_dir="23_compliance/evidence",
        )
        dashboard = ComplianceDashboardData(monitor)
        report = dashboard.generate_coverage_report()
        print(report.overall_coverage)
    """

    def __init__(self, monitor: AutomatedComplianceMonitor) -> None:
        self._monitor = monitor
        self._latest_result: Optional[MonitoringResult] = None

    def refresh(self, frameworks: Optional[list[str]] = None) -> MonitoringResult:
        """Run the monitor and cache the result."""
        self._latest_result = self._monitor.run(frameworks)
        return self._latest_result

    @property
    def latest_result(self) -> Optional[MonitoringResult]:
        return self._latest_result

    # -- framework-level aggregation ----------------------------------------

    def _build_framework_status(
        self, framework: str, findings: list[ComplianceFinding], controls: list[dict]
    ) -> FrameworkStatus:
        fw_findings = [f for f in findings if f.framework == framework]
        not_impl = sum(
            1
            for f in fw_findings
            if "no evidence" in f.description.lower()
        )
        partial = sum(
            1
            for f in fw_findings
            if "stale evidence" in f.description.lower()
        )
        total = len(controls)
        implemented = total - not_impl - partial

        critical = sum(
            1 for f in fw_findings if f.severity == Severity.CRITICAL
        )
        overdue = sum(
            1
            for f in fw_findings
            if f.due_date
            and f.due_date < datetime.now(timezone.utc).isoformat()
        )

        return FrameworkStatus(
            framework=framework,
            total_controls=total,
            implemented=max(0, implemented),
            partial=partial,
            not_implemented=not_impl,
            open_findings=len(fw_findings),
            critical_findings=critical,
            overdue_reviews=overdue,
            last_checked=datetime.now(timezone.utc).isoformat(),
        )

    # -- gap identification -------------------------------------------------

    def _identify_gaps(
        self, findings: list[ComplianceFinding]
    ) -> list[dict[str, Any]]:
        """Identify the most critical compliance gaps."""
        gaps = []
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }

        sorted_findings = sorted(
            findings,
            key=lambda f: severity_order.get(f.severity, 5),
        )

        for finding in sorted_findings:
            if finding.status == FindingStatus.OPEN:
                gaps.append(
                    {
                        "framework": finding.framework,
                        "control_id": finding.control_id,
                        "control_title": finding.control_title,
                        "severity": finding.severity.value,
                        "description": finding.description,
                        "remediation": finding.remediation,
                    }
                )
        return gaps

    def _identify_overdue(
        self, findings: list[ComplianceFinding]
    ) -> list[dict[str, Any]]:
        """Find findings that are past their due date."""
        now = datetime.now(timezone.utc).isoformat()
        overdue = []
        for f in findings:
            if f.due_date and f.due_date < now and f.status == FindingStatus.OPEN:
                overdue.append(
                    {
                        "finding_id": f.finding_id,
                        "framework": f.framework,
                        "control_id": f.control_id,
                        "due_date": f.due_date,
                        "severity": f.severity.value,
                    }
                )
        return overdue

    # -- report generation --------------------------------------------------

    def generate_coverage_report(
        self, frameworks: Optional[list[str]] = None
    ) -> CoverageReport:
        """
        Generate a comprehensive coverage report.

        If no recent monitoring result is cached, triggers a fresh run.
        """
        if self._latest_result is None:
            self.refresh(frameworks)

        assert self._latest_result is not None
        result = self._latest_result

        report = CoverageReport()
        report.total_controls_all = result.total_controls
        report.total_findings = len(result.findings)
        report.critical_findings = sum(
            1 for f in result.findings if f.severity == Severity.CRITICAL
        )

        # Build per-framework status
        fw_data = self._monitor._framework_data
        for fw_name in result.frameworks_checked:
            controls = fw_data.get(fw_name, [])
            status = self._build_framework_status(
                fw_name, result.findings, controls
            )
            report.frameworks.append(status)

        # Compute overall coverage
        if report.frameworks:
            weighted_sum = sum(
                fs.coverage_percent * fs.total_controls
                for fs in report.frameworks
            )
            total = sum(fs.total_controls for fs in report.frameworks)
            report.overall_coverage = (
                round(weighted_sum / total, 2) if total > 0 else 0.0
            )
            weighted_full = sum(
                fs.full_coverage_percent * fs.total_controls
                for fs in report.frameworks
            )
            report.overall_full_coverage = (
                round(weighted_full / total, 2) if total > 0 else 0.0
            )

        report.gaps = self._identify_gaps(result.findings)
        report.overdue_items = self._identify_overdue(result.findings)

        logger.info(
            "Coverage report generated: %.1f%% overall, %d gaps",
            report.overall_coverage,
            len(report.gaps),
        )
        return report

    def get_framework_summary(self) -> list[dict[str, Any]]:
        """Return a lightweight summary suitable for dashboard widgets."""
        report = self.generate_coverage_report()
        return [fw.to_dict() for fw in report.frameworks]


__all__ = [
    "ComplianceDashboardData",
    "FrameworkStatus",
    "CoverageReport",
]
