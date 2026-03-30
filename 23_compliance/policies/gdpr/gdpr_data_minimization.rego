# GDPR Data Minimization Policy — OPA/Rego
# Enforces Art. 5(1)(c) and Art. 25 data minimization controls
# SAFE-FIX: No PII, no secrets. Policy logic only.
# Generated: 2026-03-29 | Agent: A8-COMPLIANCE-MAPPING-CLOSURE

package ssid.compliance.gdpr.data_minimization

# Default deny — data operations must explicitly pass all checks
default allow := false

# Allow data operation if all minimization checks pass
allow if {
    is_hash_only
    no_raw_pii
    purpose_declared
    retention_within_limit
}

# Check: stored data must be hash format (SHA3-256 = 64 hex chars)
is_hash_only if {
    input.data_format == "sha3_256"
    count(input.data_value) == 64
    regex.match(`^[a-f0-9]{64}$`, input.data_value)
}

# Check: no raw PII fields present in the operation
no_raw_pii if {
    not input.contains_name
    not input.contains_address
    not input.contains_national_id
    not input.contains_email
    not input.contains_phone
    not input.contains_biometric
}

# Check: purpose must be declared and valid
purpose_declared if {
    input.purpose != ""
    input.purpose in valid_purposes
}

# Check: retention TTL within policy limits
retention_within_limit if {
    input.retention_days <= max_retention_days
}

# Valid processing purposes
valid_purposes := {
    "identity_verification",
    "kyc_attestation",
    "access_control",
    "audit_logging",
    "sanctions_screening",
    "credential_issuance",
    "selective_disclosure"
}

# Maximum retention: 1825 days (5 years) per AMLD6/FATF requirements
max_retention_days := 1825

# Violation details for audit trail
violations[msg] if {
    not is_hash_only
    msg := "DATA_MINIMIZATION_VIOLATION: Data is not in SHA3-256 hash format"
}

violations[msg] if {
    not no_raw_pii
    msg := "PII_DETECTED: Raw PII fields present in data operation"
}

violations[msg] if {
    not purpose_declared
    msg := sprintf("PURPOSE_MISSING: Purpose '%s' not declared or not in valid set", [input.purpose])
}

violations[msg] if {
    not retention_within_limit
    msg := sprintf("RETENTION_EXCEEDED: %d days exceeds maximum %d days", [input.retention_days, max_retention_days])
}

# Crypto-shredding eligibility check (GDPR Art. 17)
crypto_shred_eligible if {
    input.user_request == "erasure"
    input.has_active_salt == true
}

# DPIA required flag (GDPR Art. 35)
dpia_required if {
    input.processing_type == "automated_scoring"
}

dpia_required if {
    input.data_subjects_count > 10000
}
