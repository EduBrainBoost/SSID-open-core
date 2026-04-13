"""
Compliance Report Generator (R021)

Generates compliance reports in Markdown and JSON format with per-framework
breakdown, gap analysis, and remediation recommendations.

Exports:
    ComplianceReportGenerator
    generate_markdown_report
    generate_json_report
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .automated_compliance_monitor import (
    AutomatedComplianceMonitor,
    MonitoringResult,
)
from .compliance_dashboard_data import (
    ComplianceDashboardData,
    CoverageReport,
)

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = "23_compliance/reports"


# ---------------------------------------------------------------------------
# Markdown generation helpers
# ---------------------------------------------------------------------------


def _severity_badge(severity: str) -> str:
    badges = {
        "critical": "**[CRITICAL]**",
        "high": "**[HIGH]**",
        "medium": "[MEDIUM]",
        "low": "[LOW]",
        "info": "[INFO]",
    }
    return badges.get(severity.lower(), f"[{severity.upper()}]")


def _coverage_bar(percent: float, width: int = 20) -> str:
    filled = int(percent / 100 * width)
    empty = width - filled
    return f"[{'#' * filled}{'.' * empty}] {percent:.1f}%"


def _risk_indicator(risk: str) -> str:
    indicators = {
        "CRITICAL": "!! CRITICAL !!",
        "HIGH": "! HIGH !",
        "MEDIUM": "~ MEDIUM ~",
        "LOW": "OK",
    }
    return indicators.get(risk.upper(), risk)


# ---------------------------------------------------------------------------
# Public generation functions
# ---------------------------------------------------------------------------


def generate_markdown_report(
    report: CoverageReport,
    monitoring_result: MonitoringResult | None = None,
) -> str:
    """
    Generate a full Markdown compliance report from a CoverageReport.

    Parameters
    ----------
    report : CoverageReport
        The coverage report produced by ComplianceDashboardData.
    monitoring_result : MonitoringResult, optional
        The raw monitoring result for additional detail.

    Returns
    -------
    str
        The complete Markdown document.
    """
    lines: list[str] = []

    # -- Header -------------------------------------------------------------
    lines.append("# SSID Compliance Report")
    lines.append("")
    lines.append(f"**Generated:** {report.generated_at}")
    if monitoring_result:
        lines.append(f"**Run ID:** {monitoring_result.run_id}")
    lines.append(f"**Risk Summary:** {report.risk_summary}")
    lines.append("")

    # -- Executive Summary --------------------------------------------------
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Overall Coverage:** {report.overall_coverage:.1f}%")
    lines.append(f"- **Full Implementation Coverage:** {report.overall_full_coverage:.1f}%")
    lines.append(f"- **Total Controls Assessed:** {report.total_controls_all}")
    lines.append(f"- **Total Open Findings:** {report.total_findings}")
    lines.append(f"- **Critical Findings:** {report.critical_findings}")
    lines.append(f"- **Frameworks Assessed:** {len(report.frameworks)}")
    lines.append("")

    # -- Per-Framework Breakdown --------------------------------------------
    lines.append("## Framework Coverage")
    lines.append("")
    lines.append("| Framework | Controls | Implemented | Partial | Not Impl. | Coverage | Risk |")
    lines.append("|-----------|----------|-------------|---------|-----------|----------|------|")
    for fw in report.frameworks:
        lines.append(
            f"| {fw.framework.upper()} "
            f"| {fw.total_controls} "
            f"| {fw.implemented} "
            f"| {fw.partial} "
            f"| {fw.not_implemented} "
            f"| {_coverage_bar(fw.coverage_percent)} "
            f"| {_risk_indicator(fw.risk_level)} |"
        )
    lines.append("")

    # -- Detailed Framework Sections ----------------------------------------
    for fw in report.frameworks:
        lines.append(f"### {fw.framework.upper()}")
        lines.append("")
        lines.append(f"- **Coverage:** {fw.coverage_percent:.1f}% (full: {fw.full_coverage_percent:.1f}%)")
        lines.append(f"- **Open Findings:** {fw.open_findings}")
        lines.append(f"- **Critical Findings:** {fw.critical_findings}")
        lines.append(f"- **Overdue Reviews:** {fw.overdue_reviews}")
        lines.append(f"- **Risk Level:** {_risk_indicator(fw.risk_level)}")
        lines.append("")

    # -- Gap Analysis -------------------------------------------------------
    lines.append("## Gap Analysis")
    lines.append("")
    if report.gaps:
        lines.append(f"**{len(report.gaps)} compliance gaps identified:**")
        lines.append("")
        for i, gap in enumerate(report.gaps, 1):
            sev = _severity_badge(gap["severity"])
            lines.append(f"### Gap {i}: {gap['control_id']} - {gap['control_title']}")
            lines.append("")
            lines.append(f"- **Framework:** {gap['framework'].upper()}")
            lines.append(f"- **Severity:** {sev}")
            lines.append(f"- **Description:** {gap['description']}")
            if gap.get("remediation"):
                lines.append(f"- **Remediation:** {gap['remediation']}")
            lines.append("")
    else:
        lines.append("No compliance gaps identified. All controls have evidence.")
        lines.append("")

    # -- Overdue Reviews ----------------------------------------------------
    if report.overdue_items:
        lines.append("## Overdue Reviews")
        lines.append("")
        lines.append("| Finding ID | Framework | Control | Due Date | Severity |")
        lines.append("|------------|-----------|---------|----------|----------|")
        for item in report.overdue_items:
            lines.append(
                f"| {item['finding_id']} "
                f"| {item['framework'].upper()} "
                f"| {item['control_id']} "
                f"| {item['due_date']} "
                f"| {_severity_badge(item['severity'])} |"
            )
        lines.append("")

    # -- Remediation Recommendations ----------------------------------------
    lines.append("## Remediation Recommendations")
    lines.append("")
    lines.append("### Prioritised Actions")
    lines.append("")

    critical_gaps = [g for g in report.gaps if g["severity"] == "critical"]
    high_gaps = [g for g in report.gaps if g["severity"] == "high"]
    other_gaps = [g for g in report.gaps if g["severity"] not in ("critical", "high")]

    if critical_gaps:
        lines.append("#### Immediate (Critical)")
        lines.append("")
        for gap in critical_gaps:
            lines.append(
                f"1. **{gap['control_id']}** ({gap['framework'].upper()}): {gap.get('remediation', 'Remediation required')}"
            )
        lines.append("")

    if high_gaps:
        lines.append("#### Short-Term (High)")
        lines.append("")
        for gap in high_gaps:
            lines.append(
                f"1. **{gap['control_id']}** ({gap['framework'].upper()}): {gap.get('remediation', 'Remediation required')}"
            )
        lines.append("")

    if other_gaps:
        lines.append("#### Medium-Term (Medium/Low)")
        lines.append("")
        for gap in other_gaps:
            lines.append(
                f"1. **{gap['control_id']}** ({gap['framework'].upper()}): {gap.get('remediation', 'Review and update')}"
            )
        lines.append("")

    if not report.gaps:
        lines.append("No remediation actions required at this time.")
        lines.append("")

    # -- Footer -------------------------------------------------------------
    lines.append("---")
    lines.append("")
    lines.append(
        "*This report was generated by the SSID Automated Compliance Monitor "
        "(R021). Evidence paths reference artefacts in `23_compliance/evidence/`.*"
    )
    lines.append("")

    return "\n".join(lines)


def generate_json_report(
    report: CoverageReport,
    monitoring_result: MonitoringResult | None = None,
) -> str:
    """
    Generate a JSON compliance report from a CoverageReport.

    Returns a formatted JSON string.
    """
    output: dict[str, Any] = {
        "report_type": "ssid_compliance_report",
        "version": "1.0.0",
        "generated_at": report.generated_at,
        "risk_summary": report.risk_summary,
    }

    if monitoring_result:
        output["monitoring_run"] = {
            "run_id": monitoring_result.run_id,
            "started_at": monitoring_result.started_at,
            "completed_at": monitoring_result.completed_at,
            "pass_rate": monitoring_result.pass_rate,
        }

    output["summary"] = {
        "overall_coverage": report.overall_coverage,
        "overall_full_coverage": report.overall_full_coverage,
        "total_controls": report.total_controls_all,
        "total_findings": report.total_findings,
        "critical_findings": report.critical_findings,
        "frameworks_assessed": len(report.frameworks),
    }

    output["frameworks"] = [fw.to_dict() for fw in report.frameworks]
    output["gaps"] = report.gaps
    output["overdue_items"] = report.overdue_items

    if monitoring_result:
        output["findings"] = [f.to_dict() for f in monitoring_result.findings]

    return json.dumps(output, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Report generator class
# ---------------------------------------------------------------------------


class ComplianceReportGenerator:
    """
    High-level report generator that wraps the monitor and dashboard.

    Usage::

        generator = ComplianceReportGenerator(
            frameworks_dir="23_compliance/frameworks",
            evidence_dir="23_compliance/evidence",
            output_dir="23_compliance/reports",
        )
        md = generator.generate(format="markdown")
        generator.save_report(md, "compliance_report.md")
    """

    def __init__(
        self,
        frameworks_dir: str,
        evidence_dir: str,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        config_path: str | None = None,
    ) -> None:
        self._monitor = AutomatedComplianceMonitor(
            frameworks_dir=frameworks_dir,
            evidence_dir=evidence_dir,
            config_path=config_path,
        )
        self._dashboard = ComplianceDashboardData(self._monitor)
        self._output_dir = Path(output_dir)

    def generate(
        self,
        format: str = "markdown",
        frameworks: list[str] | None = None,
    ) -> str:
        """
        Run the monitor and generate a report.

        Parameters
        ----------
        format : str
            Either ``"markdown"`` or ``"json"``.
        frameworks : list[str], optional
            Subset of frameworks to check.

        Returns
        -------
        str
            The generated report content.
        """
        result = self._dashboard.refresh(frameworks)
        report = self._dashboard.generate_coverage_report(frameworks)

        if format == "json":
            return generate_json_report(report, result)
        return generate_markdown_report(report, result)

    def save_report(self, content: str, filename: str) -> Path:
        """Write report content to the output directory."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self._output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        logger.info("Report saved to %s", filepath)
        return filepath

    def generate_and_save(
        self,
        frameworks: list[str] | None = None,
        prefix: str = "compliance_report",
    ) -> tuple[Path, Path]:
        """
        Generate both Markdown and JSON reports and save them.

        Returns tuple of (markdown_path, json_path).
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        md_content = self.generate(format="markdown", frameworks=frameworks)
        md_path = self.save_report(md_content, f"{prefix}_{timestamp}.md")

        json_content = self.generate(format="json", frameworks=frameworks)
        json_path = self.save_report(json_content, f"{prefix}_{timestamp}.json")

        return md_path, json_path


__all__ = [
    "ComplianceReportGenerator",
    "generate_markdown_report",
    "generate_json_report",
]
