package ssid.codex.contracts

# Codex Contract Policy — OPA/Rego
# ROOT-24-LOCK | Module: 16_codex | SoT v4.1.0
#
# Enforces non-custodial and hash-only constraints for Codex contracts.

import future.keywords.if
import future.keywords.in

default allow := false
default compliant := false

# -------------------------------------------------------------------
# Non-custodial enforcement
# -------------------------------------------------------------------

# Codex contracts must never hold or transfer funds
non_custodial_violation if {
    input.contract.holds_funds == true
}

non_custodial_violation if {
    input.contract.transfers_funds == true
}

# -------------------------------------------------------------------
# Hash-only evidence
# -------------------------------------------------------------------

# All stored data must be hashes, not raw PII
pii_violation if {
    some field in input.contract.stored_fields
    field.type != "bytes32"
    field.type != "uint256"
    field.type != "address"
    field.type != "bool"
    field.type != "string"
    field.contains_pii == true
}

# -------------------------------------------------------------------
# Version enforcement
# -------------------------------------------------------------------

version_compliant if {
    input.contract.version == "4.1.0"
}

# -------------------------------------------------------------------
# Governance access control
# -------------------------------------------------------------------

governance_enforced if {
    input.contract.has_governance_modifier == true
    input.contract.registration_restricted == true
}

# -------------------------------------------------------------------
# Combined compliance
# -------------------------------------------------------------------

compliant if {
    not non_custodial_violation
    not pii_violation
    version_compliant
    governance_enforced
}

allow if {
    compliant
}

# -------------------------------------------------------------------
# Violations report
# -------------------------------------------------------------------

violations[msg] if {
    non_custodial_violation
    msg := "NON_CUSTODIAL: Contract holds or transfers funds"
}

violations[msg] if {
    pii_violation
    msg := "PII_VIOLATION: Contract stores raw PII data"
}

violations[msg] if {
    not version_compliant
    msg := sprintf("VERSION_MISMATCH: Expected 4.1.0, got %s", [input.contract.version])
}

violations[msg] if {
    not governance_enforced
    msg := "GOVERNANCE_MISSING: Registration not restricted to governance"
}
