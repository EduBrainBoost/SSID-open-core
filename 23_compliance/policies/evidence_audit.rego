package policies.evidence_audit

# Policy: EVIDENCE_AUDIT_001
# Name: Evidence & Audit

violation[msg] {
    input.evidence.hashed == false
    msg := "EVIDENCE_AUDIT_001: Evidence must be hashed"
}

violation[msg] {
    input.evidence.ledger_enabled == false
    msg := "EVIDENCE_AUDIT_001: Hash-ledger required"
}

violation[msg] {
    input.evidence.blockchain_anchoring_enabled == false
    msg := "EVIDENCE_AUDIT_001: Blockchain anchoring required"
}

violation[msg] {
    input.evidence.worm_storage_enabled == false
    msg := "EVIDENCE_AUDIT_001: WORM storage required"
}

violation[msg] {
    input.evidence.retention_years < 10
    msg := "EVIDENCE_AUDIT_001: 10-year retention minimum"
}

compliant {
    count(violation) == 0
}
