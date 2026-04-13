# AML/KYC Gate Policy — OPA/Rego
# Enforces AMLD6 / FATF Travel Rule KYC requirements
# SAFE-FIX: No PII, no secrets. Policy logic only.
# Generated: 2026-03-29 | Agent: A8-COMPLIANCE-MAPPING-CLOSURE

package ssid.compliance.aml.kyc_gate

# Default deny — all identity operations must pass KYC gate
default allow := false
default risk_level := "unknown"

# Allow if KYC verification passed and sanctions clear
allow if {
    kyc_verified
    sanctions_clear
    not jurisdiction_blocked
    risk_level != "prohibited"
}

# KYC verification check
kyc_verified if {
    input.kyc_status == "verified"
    input.kyc_provider != ""
    input.kyc_attestation_hash != ""
    valid_attestation_format(input.kyc_attestation_hash)
}

# Attestation must be SHA3-256 hash format
valid_attestation_format(hash) if {
    count(hash) == 64
    regex.match(`^[a-f0-9]{64}$`, hash)
}

# Sanctions screening passed
sanctions_clear if {
    input.sanctions_status == "clear"
    input.sanctions_check_timestamp != ""
    sanctions_check_not_stale
}

# Sanctions check must be within 24 hours
sanctions_check_not_stale if {
    time.now_ns() - time.parse_rfc3339_ns(input.sanctions_check_timestamp) < 86400000000000
}

# Jurisdiction not blocked
jurisdiction_blocked if {
    input.jurisdiction in blocked_jurisdictions
}

# Risk level determination per AMLD6 risk-based approach
risk_level := "low" if {
    input.jurisdiction in low_risk_jurisdictions
    input.transaction_value < 1000
}

risk_level := "standard" if {
    not input.jurisdiction in low_risk_jurisdictions
    not input.jurisdiction in high_risk_jurisdictions
    input.transaction_value < 15000
}

risk_level := "enhanced" if {
    input.jurisdiction in high_risk_jurisdictions
}

risk_level := "enhanced" if {
    input.transaction_value >= 15000
}

risk_level := "prohibited" if {
    input.jurisdiction in blocked_jurisdictions
}

# Enhanced Due Diligence (EDD) required
edd_required if {
    risk_level == "enhanced"
}

edd_required if {
    input.pep_status == true
}

edd_required if {
    input.adverse_media == true
}

edd_required if {
    input.jurisdiction in project_restricted_jurisdictions
}

# CDD tier mapping
cdd_tier := "simplified" if {
    risk_level == "low"
    not edd_required
}

cdd_tier := "standard" if {
    risk_level == "standard"
    not edd_required
}

cdd_tier := "enhanced" if {
    edd_required
}

# Travel Rule applicability (FATF R.16)
travel_rule_applicable if {
    input.transaction_value >= 1000
    input.transaction_type == "cross_border"
}

# Travel Rule data requirements
travel_rule_compliant if {
    travel_rule_applicable
    input.originator_attestation_hash != ""
    input.beneficiary_attestation_hash != ""
    valid_attestation_format(input.originator_attestation_hash)
    valid_attestation_format(input.beneficiary_attestation_hash)
}

# Non-custodial exemption assessment
non_custodial_vasp_exempt if {
    input.ssid_role == "infrastructure_provider"
    input.holds_user_funds == false
    input.executes_transactions == false
}

# FATF high-risk jurisdictions (FATF grey/black list)
# Synced with 23_compliance/policies/jurisdiction_blacklist.yaml high_risk
# AF, BY, MM, RU, VE, YE, ZW — enhanced_due_diligence enforcement
high_risk_jurisdictions := {
    "AF", "BY", "MM", "RU", "VE", "YE", "ZW"
}

# Blocked jurisdictions (comprehensive sanctions + sanctioned regions)
# Synced with 23_compliance/policies/jurisdiction_blacklist.yaml
# fully_sanctioned: IR, KP, SY, CU
# sanctioned_regions: RU_CRIMEA, RU_DNR, RU_LNR
blocked_jurisdictions := {
    "IR", "KP", "SY", "CU",
    "RU_CRIMEA", "RU_DNR", "RU_LNR"
}

# Project-restricted jurisdictions (SSID project rule, NOT international sanctions)
# These jurisdictions are restricted per SSID governance decision due to elevated
# regulatory complexity. They are NOT OFAC/EU/UN sanctioned. Enforcement requires
# enhanced due diligence for all credential operations.
# Synced with 23_compliance/policies/jurisdiction_blacklist.yaml project_restricted
project_restricted_jurisdictions := {
    "IN", "PK"
}

# Deny rule for project-restricted jurisdictions without EDD completion
# Unlike blocked_jurisdictions (hard deny), project_restricted allows operations
# if enhanced_due_diligence has been completed and approved.
jurisdiction_project_restricted if {
    input.jurisdiction in project_restricted_jurisdictions
}

risk_level := "enhanced" if {
    input.jurisdiction in project_restricted_jurisdictions
}

# Low-risk jurisdictions (EU/EEA + equivalent)
low_risk_jurisdictions := {
    "DE", "FR", "NL", "AT", "BE", "FI", "SE", "DK",
    "IE", "LU", "IT", "ES", "PT", "CH", "NO", "IS",
    "LI", "SG", "JP", "AU", "CA", "NZ", "GB"
}

# Violations for audit trail
violations[msg] if {
    not kyc_verified
    msg := "AML_KYC_GATE: KYC verification not passed"
}

violations[msg] if {
    not sanctions_clear
    msg := "AML_SANCTIONS: Sanctions screening not clear or stale"
}

violations[msg] if {
    jurisdiction_blocked
    msg := sprintf("AML_JURISDICTION: Jurisdiction %s is blocked", [input.jurisdiction])
}

violations[msg] if {
    travel_rule_applicable
    not travel_rule_compliant
    msg := "FATF_TRAVEL_RULE: Cross-border transaction lacks required attestation data"
}

violations[msg] if {
    edd_required
    input.edd_completed != true
    msg := "AML_EDD: Enhanced due diligence required but not completed"
}

violations[msg] if {
    jurisdiction_project_restricted
    input.edd_completed != true
    msg := sprintf("AML_PROJECT_RESTRICTED: Jurisdiction %s is project-restricted (SSID rule, not international sanction) — EDD required", [input.jurisdiction])
}
