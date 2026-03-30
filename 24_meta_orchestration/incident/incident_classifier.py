"""
SSID Incident Classifier — deterministic, fail-closed classification.

Classifies incidents into SEV-1 through SEV-4 based on incident type
and reported severity. stdlib-only, no mainnet actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

# --- Canonical incident types ---------------------------------------------------

INCIDENT_TYPES: set[str] = {
    "service_down",
    "login_failure",
    "session_break",
    "queue_stuck",
    "stale_lock",
    "provider_failure",
    "evidence_persistence_failure",
    "config_drift",
}

# --- Severity matrix (type -> base SEV) ----------------------------------------
# Lower number = higher severity.  The matrix is intentionally static so that
# classification is fully deterministic and auditable.

_BASE_SEVERITY: dict[str, int] = {
    "service_down":                  1,
    "evidence_persistence_failure":  1,
    "provider_failure":              2,
    "login_failure":                 2,
    "session_break":                 2,
    "queue_stuck":                   3,
    "stale_lock":                    3,
    "config_drift":                  4,
}

VALID_SEVERITIES: set[str] = {"critical", "high", "medium", "low"}

# Severity modifier: reported severity can shift the base by at most +/-1
_SEVERITY_MODIFIER: dict[str, int] = {
    "critical": -1,
    "high":      0,
    "medium":    1,
    "low":       1,
}


# --- Data model -----------------------------------------------------------------

@dataclass
class Incident:
    """Immutable incident record produced by classify()."""

    incident_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_type: str = ""
    reported_severity: str = ""
    sev_level: int = 1          # 1-4
    sev_label: str = "SEV-1"    # human-readable
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    description: Optional[str] = None
    containment_status: str = "pending"
    diagnosis: Optional[str] = None
    repair_action: Optional[str] = None
    verified: bool = False


# --- Public API -----------------------------------------------------------------

def classify(
    incident_type: str,
    severity: str,
    description: Optional[str] = None,
) -> Incident:
    """Classify an incident deterministically into SEV-1..SEV-4.

    Fail-closed: unknown types or severities default to SEV-1.
    """
    # Fail-closed: unknown type -> SEV-1
    if incident_type not in INCIDENT_TYPES:
        return Incident(
            incident_type=incident_type,
            reported_severity=severity,
            sev_level=1,
            sev_label="SEV-1",
            description=description or f"UNKNOWN incident type: {incident_type}",
        )

    # Fail-closed: unknown severity -> treat as critical
    if severity not in VALID_SEVERITIES:
        severity = "critical"

    base = _BASE_SEVERITY[incident_type]
    modifier = _SEVERITY_MODIFIER[severity]
    level = max(1, min(4, base + modifier))

    return Incident(
        incident_type=incident_type,
        reported_severity=severity,
        sev_level=level,
        sev_label=f"SEV-{level}",
        description=description,
    )
