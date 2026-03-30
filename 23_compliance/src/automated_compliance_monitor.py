"""
Automated Compliance Monitor (R021)

Periodically checks all compliance frameworks (MiCA, eIDAS, GDPR, FATF, AMLD6)
against evidence records and generates structured compliance findings.

Exports:
    AutomatedComplianceMonitor
    ComplianceFinding
    MonitoringResult
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRAMEWORKS_DIR_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "frameworks"
)
EVIDENCE_DIR_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "evidence"
)

SUPPORTED_FRAMEWORKS = ("mica", "eidas", "gdpr", "fatf", "amld6")


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    OPEN = "open"
    REMEDIATED = "remediated"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"


class ControlStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ComplianceFinding:
    """A single compliance finding produced by the monitor."""

    finding_id: str
    framework: str
    control_id: str
    control_title: str
    status: FindingStatus
    severity: Severity
    description: str
    evidence_ref: Optional[str] = None
    remediation: Optional[str] = None
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    due_date: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "framework": self.framework,
            "control_id": self.control_id,
            "control_title": self.control_title,
            "status": self.status.value,
            "severity": self.severity.value,
            "description": self.description,
            "evidence_ref": self.evidence_ref,
            "remediation": self.remediation,
            "detected_at": self.detected_at,
            "due_date": self.due_date,
        }


@dataclass
class MonitoringResult:
    """Aggregate result of one monitoring cycle across all frameworks."""

    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    frameworks_checked: list[str] = field(default_factory=list)
    total_controls: int = 0
    controls_passing: int = 0
    controls_failing: int = 0
    controls_partial: int = 0
    findings: list[ComplianceFinding] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_controls == 0:
            return 0.0
        return round(self.controls_passing / self.total_controls * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "frameworks_checked": self.frameworks_checked,
            "total_controls": self.total_controls,
            "controls_passing": self.controls_passing,
            "controls_failing": self.controls_failing,
            "controls_partial": self.controls_partial,
            "pass_rate": self.pass_rate,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class AutomatedComplianceMonitor:
    """
    Reads framework YAML definitions from ``23_compliance/frameworks/``,
    correlates them with evidence artefacts, and produces
    :class:`ComplianceFinding` objects for every control that is missing,
    partial, or overdue for review.
    """

    def __init__(
        self,
        frameworks_dir: str = FRAMEWORKS_DIR_DEFAULT,
        evidence_dir: str = EVIDENCE_DIR_DEFAULT,
        config_path: Optional[str] = None,
    ) -> None:
        self.frameworks_dir = Path(frameworks_dir)
        self.evidence_dir = Path(evidence_dir)
        self._config: dict[str, Any] = {}
        self._framework_data: dict[str, list[dict]] = {}

        if config_path:
            self._load_config(config_path)

    # -- configuration ------------------------------------------------------

    def _load_config(self, path: str) -> None:
        config_file = Path(path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as fh:
                self._config = yaml.safe_load(fh) or {}
            logger.info("Loaded compliance monitor config from %s", path)
        else:
            logger.warning("Config file not found: %s", path)

    @property
    def check_interval_hours(self) -> int:
        schedule = self._config.get("monitoring_schedule", {})
        return int(schedule.get("interval_hours", 24))

    @property
    def alert_channels(self) -> list[str]:
        return self._config.get("alert_channels", [])

    # -- framework loading --------------------------------------------------

    def _load_framework_controls(self, framework_name: str) -> list[dict]:
        """Load control definitions from a framework's YAML files."""
        fw_dir = self.frameworks_dir / framework_name
        if not fw_dir.is_dir():
            logger.warning("Framework directory not found: %s", fw_dir)
            return []

        controls: list[dict] = []
        for yaml_file in sorted(fw_dir.glob("*.yaml")):
            with open(yaml_file, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if not data:
                continue

            # Support both top-level list and nested 'controls' key
            if isinstance(data, list):
                controls.extend(data)
            elif isinstance(data, dict):
                if "controls" in data and isinstance(data["controls"], list):
                    controls.extend(data["controls"])
                elif "mappings" in data and isinstance(data["mappings"], list):
                    # mapping files: each mapping entry may contain control refs
                    for mapping in data["mappings"]:
                        if "control_id" in mapping:
                            controls.append(mapping)

        return controls

    def load_all_frameworks(
        self, frameworks: Optional[list[str]] = None
    ) -> dict[str, list[dict]]:
        """Load controls for the requested (or all supported) frameworks."""
        targets = frameworks or list(SUPPORTED_FRAMEWORKS)
        self._framework_data = {}
        for fw in targets:
            self._framework_data[fw] = self._load_framework_controls(fw)
            logger.info(
                "Loaded %d controls for framework '%s'",
                len(self._framework_data[fw]),
                fw,
            )
        return self._framework_data

    # -- evidence checking --------------------------------------------------

    def _find_evidence_for_control(
        self, framework: str, control_id: str
    ) -> Optional[str]:
        """
        Look for an evidence file matching the control in the evidence
        directory tree. Returns the evidence file path if found, else None.
        """
        evidence_base = self.evidence_dir
        if not evidence_base.is_dir():
            return None

        # Search patterns: framework subfolder, then global
        search_dirs = [evidence_base / framework, evidence_base]
        normalised = control_id.lower().replace(".", "_").replace("-", "_")

        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for candidate in search_dir.rglob("*"):
                if candidate.is_file() and normalised in candidate.stem.lower():
                    return str(candidate)
        return None

    def _check_evidence_freshness(
        self, evidence_path: str, max_age_days: int = 90
    ) -> bool:
        """Return True if evidence file was modified within max_age_days."""
        try:
            mtime = os.path.getmtime(evidence_path)
            age = datetime.now(timezone.utc) - datetime.fromtimestamp(
                mtime, tz=timezone.utc
            )
            return age <= timedelta(days=max_age_days)
        except OSError:
            return False

    def _evaluate_control(
        self, framework: str, control: dict
    ) -> tuple[ControlStatus, Optional[str]]:
        """
        Evaluate a single control against available evidence.

        Returns (status, evidence_path).
        """
        control_id = control.get("control_id", control.get("id", "UNKNOWN"))
        evidence_path = self._find_evidence_for_control(framework, control_id)

        if evidence_path is None:
            return ControlStatus.NOT_IMPLEMENTED, None

        if not self._check_evidence_freshness(evidence_path):
            return ControlStatus.PARTIAL, evidence_path

        return ControlStatus.IMPLEMENTED, evidence_path

    # -- finding generation -------------------------------------------------

    @staticmethod
    def _generate_finding_id(framework: str, control_id: str) -> str:
        seed = f"{framework}:{control_id}:{datetime.now(timezone.utc).date()}"
        return "CF-" + hashlib.sha256(seed.encode()).hexdigest()[:12].upper()

    def _severity_for_control(self, control: dict) -> Severity:
        raw = control.get("severity", control.get("risk_level", "medium"))
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return mapping.get(str(raw).lower(), Severity.MEDIUM)

    def _create_finding(
        self,
        framework: str,
        control: dict,
        status: ControlStatus,
        evidence_path: Optional[str],
    ) -> ComplianceFinding:
        control_id = control.get("control_id", control.get("id", "UNKNOWN"))
        title = control.get("title", control.get("description", control_id))
        severity = self._severity_for_control(control)

        if status == ControlStatus.NOT_IMPLEMENTED:
            description = (
                f"Control {control_id} ({title}) has no evidence artefact. "
                f"Framework '{framework}' requires implementation."
            )
            remediation = (
                f"Implement control {control_id} and provide evidence "
                f"in 23_compliance/evidence/{framework}/"
            )
        elif status == ControlStatus.PARTIAL:
            description = (
                f"Control {control_id} ({title}) has stale evidence "
                f"(older than 90 days). Review required."
            )
            remediation = (
                f"Update evidence for {control_id} and re-verify implementation."
            )
        else:
            description = f"Control {control_id} ({title}) status: {status.value}"
            remediation = None

        return ComplianceFinding(
            finding_id=self._generate_finding_id(framework, control_id),
            framework=framework,
            control_id=control_id,
            control_title=title,
            status=FindingStatus.OPEN,
            severity=severity,
            description=description,
            evidence_ref=evidence_path,
            remediation=remediation,
        )

    # -- main run -----------------------------------------------------------

    def run(
        self, frameworks: Optional[list[str]] = None
    ) -> MonitoringResult:
        """
        Execute a full monitoring cycle.

        1. Load framework definitions.
        2. For each control, check evidence.
        3. Generate findings for non-compliant controls.
        4. Return aggregated :class:`MonitoringResult`.
        """
        run_id = (
            "MON-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        )
        result = MonitoringResult(
            run_id=run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self.load_all_frameworks(frameworks)

        for fw_name, controls in self._framework_data.items():
            result.frameworks_checked.append(fw_name)
            for control in controls:
                result.total_controls += 1
                status, evidence_path = self._evaluate_control(fw_name, control)

                if status == ControlStatus.IMPLEMENTED:
                    result.controls_passing += 1
                elif status == ControlStatus.PARTIAL:
                    result.controls_partial += 1
                    finding = self._create_finding(
                        fw_name, control, status, evidence_path
                    )
                    result.findings.append(finding)
                elif status == ControlStatus.NOT_IMPLEMENTED:
                    result.controls_failing += 1
                    finding = self._create_finding(
                        fw_name, control, status, evidence_path
                    )
                    result.findings.append(finding)

        result.completed_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "Monitoring run %s complete: %d controls, %d passing, %d findings",
            run_id,
            result.total_controls,
            result.controls_passing,
            len(result.findings),
        )
        return result


__all__ = [
    "AutomatedComplianceMonitor",
    "ComplianceFinding",
    "MonitoringResult",
    "Severity",
    "FindingStatus",
    "ControlStatus",
]
