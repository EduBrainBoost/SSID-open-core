package sot.convergence

# SSID SoT Convergence Policy v1.0
# Evaluates convergence manifests against compliance rules.
# Input: a convergence manifest conforming to convergence_manifest_schema.json

import future.keywords.in
import future.keywords.contains
import future.keywords.if
import future.keywords.every

# ──────────────────────────────────────────────
# DENY rules — hard failures that block merges
# ──────────────────────────────────────────────

# D-001: Overall status FAIL is an unconditional deny.
deny contains msg if {
    input.status == "FAIL"
    msg := sprintf("CONVERGENCE_DENY: repo %s reported status FAIL", [input.repo_name])
}

# D-002: Canonical repos must not have missing artifacts.
deny contains msg if {
    input.repo_role == "canonical"
    count(input.missing_artifacts) > 0
    msg := sprintf(
        "CONVERGENCE_DENY: canonical repo %s has %d missing artifacts: %v",
        [input.repo_name, count(input.missing_artifacts), input.missing_artifacts]
    )
}

# D-003: Protected scope attempts are always denied.
deny contains msg if {
    some finding in input.drift_findings
    finding.class == "protected_scope_attempt"
    msg := sprintf(
        "CONVERGENCE_DENY: protected scope attempt in %s — %s (severity: %s)",
        [finding.path, finding.detail, finding.severity]
    )
}

# D-004: Critical-severity drift findings are denied.
deny contains msg if {
    some finding in input.drift_findings
    finding.severity == "critical"
    msg := sprintf(
        "CONVERGENCE_DENY: critical drift in %s — %s (class: %s)",
        [finding.path, finding.detail, finding.class]
    )
}

# ──────────────────────────────────────────────
# WARN rules — advisory, do not block
# ──────────────────────────────────────────────

# W-001: Any drift findings present trigger a warning.
warn contains msg if {
    count(input.drift_findings) > 0
    msg := sprintf(
        "CONVERGENCE_WARN: repo %s has %d drift findings",
        [input.repo_name, count(input.drift_findings)]
    )
}

# W-002: Derivative repos that are not export-ready.
warn contains msg if {
    input.repo_role == "derivative"
    input.export_ready == false
    msg := sprintf(
        "CONVERGENCE_WARN: derivative repo %s is not export-ready",
        [input.repo_name]
    )
}

# W-003: High-severity drift findings.
warn contains msg if {
    some finding in input.drift_findings
    finding.severity == "high"
    msg := sprintf(
        "CONVERGENCE_WARN: high-severity drift in %s — %s (class: %s)",
        [finding.path, finding.detail, finding.class]
    )
}

# W-004: Stale derivative binding.
warn contains msg if {
    some finding in input.drift_findings
    finding.class == "stale_derivative_binding"
    msg := sprintf(
        "CONVERGENCE_WARN: stale derivative binding at %s — %s",
        [finding.path, finding.detail]
    )
}

# ──────────────────────────────────────────────
# INFO rules — informational, for audit trails
# ──────────────────────────────────────────────

# I-001: Enforcement gap findings surfaced as info.
info contains msg if {
    some finding in input.drift_findings
    finding.class == "enforcement_gap"
    msg := sprintf(
        "CONVERGENCE_INFO: enforcement gap at %s — %s (severity: %s)",
        [finding.path, finding.detail, finding.severity]
    )
}

# I-002: Medium/low drift findings as info.
info contains msg if {
    some finding in input.drift_findings
    finding.severity == "medium"
    msg := sprintf(
        "CONVERGENCE_INFO: medium drift in %s — %s (class: %s)",
        [finding.path, finding.detail, finding.class]
    )
}

info contains msg if {
    some finding in input.drift_findings
    finding.severity == "low"
    msg := sprintf(
        "CONVERGENCE_INFO: low drift in %s — %s (class: %s)",
        [finding.path, finding.detail, finding.class]
    )
}

# ──────────────────────────────────────────────
# Summary helpers
# ──────────────────────────────────────────────

# True when no deny rules fire.
compliant if {
    count(deny) == 0
}

# Counts by severity for reporting.
critical_count := count([f | some f in input.drift_findings; f.severity == "critical"])
high_count := count([f | some f in input.drift_findings; f.severity == "high"])
medium_count := count([f | some f in input.drift_findings; f.severity == "medium"])
low_count := count([f | some f in input.drift_findings; f.severity == "low"])
