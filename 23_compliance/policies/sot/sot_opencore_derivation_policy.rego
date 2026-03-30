package sot.opencore_derivation

# SSID Open-Core Derivation Policy v1.0
# Evaluates export sync manifests against derivation compliance rules.
# Input: an export sync manifest conforming to export_sync_manifest_schema.json

import future.keywords.in
import future.keywords.contains
import future.keywords.if
import future.keywords.every

# ──────────────────────────────────────────────
# DENY rules — hard failures that block exports
# ──────────────────────────────────────────────

# D-001: Forbidden export findings are unconditional deny.
deny contains msg if {
    some finding in input.findings
    finding.class == "forbidden_export"
    msg := sprintf(
        "DERIVATION_DENY: forbidden artifact leaked to derivative — %s (path: %s)",
        [finding.detail, finding.path]
    )
}

# D-002: Contract hash mismatch is unconditional deny.
deny contains msg if {
    some finding in input.findings
    finding.class == "contract_hash_mismatch"
    msg := sprintf(
        "DERIVATION_DENY: contract hash mismatch — %s (path: %s)",
        [finding.detail, finding.path]
    )
}

# D-003: Critical stale derivative bindings are denied.
deny contains msg if {
    some finding in input.findings
    finding.class == "stale_derivative_binding"
    finding.severity == "critical"
    msg := sprintf(
        "DERIVATION_DENY: critical stale derivative binding — %s (path: %s)",
        [finding.detail, finding.path]
    )
}

# D-004: Export scope violations are denied.
deny contains msg if {
    some finding in input.findings
    finding.class == "export_scope_violation"
    msg := sprintf(
        "DERIVATION_DENY: export scope violation — %s (path: %s)",
        [finding.detail, finding.path]
    )
}

# D-005: Overall status FAIL is an unconditional deny.
deny contains msg if {
    input.status == "fail"
    msg := sprintf(
        "DERIVATION_DENY: overall sync status is FAIL for %s -> %s",
        [input.canonical_repo, input.derivative_repo]
    )
}

# ──────────────────────────────────────────────
# WARN rules — advisory, do not block
# ──────────────────────────────────────────────

# W-001: Missing expected exports.
warn contains msg if {
    some finding in input.findings
    finding.class == "missing_expected_export"
    msg := sprintf(
        "DERIVATION_WARN: expected public artifact missing from derivative — %s (path: %s)",
        [finding.detail, finding.path]
    )
}

# W-002: Registry binding missing or inconsistent.
warn contains msg if {
    some finding in input.findings
    finding.class == "registry_binding_missing"
    msg := sprintf(
        "DERIVATION_WARN: registry binding issue — %s (path: %s)",
        [finding.detail, finding.path]
    )
}

# W-003: Registry binding status is inconsistent at manifest level.
warn contains msg if {
    input.registry_binding_status == "inconsistent"
    msg := sprintf(
        "DERIVATION_WARN: registry bindings inconsistent between %s and %s",
        [input.canonical_repo, input.derivative_repo]
    )
}

# W-004: Non-critical stale derivative bindings.
warn contains msg if {
    some finding in input.findings
    finding.class == "stale_derivative_binding"
    finding.severity != "critical"
    msg := sprintf(
        "DERIVATION_WARN: stale derivative binding — %s (path: %s, severity: %s)",
        [finding.detail, finding.path, finding.severity]
    )
}

# W-005: Unsanctioned public artifacts.
warn contains msg if {
    some finding in input.findings
    finding.class == "unsanctioned_public_artifact"
    msg := sprintf(
        "DERIVATION_WARN: unsanctioned artifact in derivative — %s (path: %s)",
        [finding.detail, finding.path]
    )
}

# ──────────────────────────────────────────────
# INFO rules — informational, for audit trails
# ──────────────────────────────────────────────

# I-001: Partial export readiness (some missing but no critical failures).
info contains msg if {
    count(input.missing_exports) > 0
    count(input.forbidden_exports) == 0
    msg := sprintf(
        "DERIVATION_INFO: partial export — %d of %d allowed artifacts present in derivative",
        [count(input.actual_exports), count(input.allowed_exports)]
    )
}

# I-002: Full export completeness achieved.
info contains msg if {
    count(input.missing_exports) == 0
    count(input.forbidden_exports) == 0
    msg := sprintf(
        "DERIVATION_INFO: full export completeness — all %d allowed artifacts present",
        [count(input.allowed_exports)]
    )
}

# I-003: Registry binding status is unknown.
info contains msg if {
    input.registry_binding_status == "unknown"
    msg := "DERIVATION_INFO: registry binding status unknown — canonical registry may be absent"
}

# I-004: Derivation mode for audit record.
info contains msg if {
    msg := sprintf(
        "DERIVATION_INFO: derivation mode is '%s' for %s -> %s",
        [input.derivation_mode, input.canonical_repo, input.derivative_repo]
    )
}

# ──────────────────────────────────────────────
# Summary helpers
# ──────────────────────────────────────────────

# True when no deny rules fire.
compliant if {
    count(deny) == 0
}

# Counts by finding class for reporting.
forbidden_count := count([f | some f in input.findings; f.class == "forbidden_export"])
missing_count := count([f | some f in input.findings; f.class == "missing_expected_export"])
stale_count := count([f | some f in input.findings; f.class == "stale_derivative_binding"])
mismatch_count := count([f | some f in input.findings; f.class == "contract_hash_mismatch"])
unsanctioned_count := count([f | some f in input.findings; f.class == "unsanctioned_public_artifact"])
scope_violation_count := count([f | some f in input.findings; f.class == "export_scope_violation"])
registry_issue_count := count([f | some f in input.findings; f.class == "registry_binding_missing"])
