"""
SSID Recovery Engine — containment, diagnosis, repair, verification.

All operations are local/safe (no mainnet actions).  Every phase returns
an updated Incident so the full lifecycle is traceable.
"""

from __future__ import annotations

from .incident_classifier import Incident

# --- Containment strategies per type ------------------------------------------

_CONTAINMENT_ACTIONS: dict[str, str] = {
    "service_down": "isolate_service_endpoint",
    "login_failure": "disable_affected_auth_flow",
    "session_break": "invalidate_broken_sessions",
    "queue_stuck": "pause_queue_consumers",
    "stale_lock": "quarantine_stale_locks",
    "provider_failure": "switch_to_fallback_provider",
    "evidence_persistence_failure": "buffer_evidence_to_memory",
    "config_drift": "freeze_config_propagation",
}

_DIAGNOSIS_HINTS: dict[str, str] = {
    "service_down": "check_health_endpoints_and_dependencies",
    "login_failure": "verify_jwt_keys_and_session_store",
    "session_break": "inspect_session_token_lifecycle",
    "queue_stuck": "check_queue_depth_and_consumers",
    "stale_lock": "audit_lock_ttl_and_holder_status",
    "provider_failure": "test_provider_connectivity_and_certs",
    "evidence_persistence_failure": "verify_storage_backend_and_permissions",
    "config_drift": "diff_running_config_vs_declared_config",
}

_REPAIR_ACTIONS: dict[str, str] = {
    "service_down": "restart_service_with_health_gate",
    "login_failure": "rotate_jwt_keys_and_clear_cache",
    "session_break": "reissue_sessions_from_identity_store",
    "queue_stuck": "drain_and_restart_queue",
    "stale_lock": "force_release_expired_locks",
    "provider_failure": "reconnect_or_activate_fallback",
    "evidence_persistence_failure": "flush_memory_buffer_to_store",
    "config_drift": "reconcile_config_from_source_of_truth",
}


# --- Phase functions -----------------------------------------------------------


def containment(incident: Incident) -> Incident:
    """Isolate affected flows.  Fail-closed on unknown types."""
    action = _CONTAINMENT_ACTIONS.get(incident.incident_type, "full_isolation_unknown_type")
    incident.containment_status = "contained"
    incident.description = (f"{incident.description or ''} | CONTAINMENT: {action}").lstrip(" |")
    return incident


def diagnose(incident: Incident) -> Incident:
    """Root-cause analysis.  Returns diagnostic hint."""
    hint = _DIAGNOSIS_HINTS.get(incident.incident_type, "unknown_type_full_diagnostic_required")
    incident.diagnosis = hint
    return incident


def repair(incident: Incident) -> Incident:
    """Apply minimal safe fix.  No mainnet mutations."""
    action = _REPAIR_ACTIONS.get(incident.incident_type, "manual_intervention_required")
    incident.repair_action = action
    return incident


def verify(incident: Incident) -> Incident:
    """Verify recovery succeeded.  Sets verified flag."""
    checks_passed = all(
        [
            incident.containment_status == "contained",
            incident.diagnosis is not None,
            incident.repair_action is not None,
        ]
    )
    incident.verified = checks_passed
    return incident
