package policies.gdpr

# Policy: GDPR_ERASURE_001
# Name: GDPR Right to Erasure
# Rule: Hash-Rotation macht alte Hashes unbrauchbar

import data.compliance.constants

violation[msg] {
    input.gdpr.pepper_rotation_enabled == false
    msg := "GDPR_ERASURE_001: Pepper rotation must be enabled"
}

violation[msg] {
    input.gdpr.pepper_versioning == false
    msg := "GDPR_ERASURE_001: Pepper version tracking required"
}

violation[msg] {
    input.gdpr.data_retention_policy == ""
    msg := "GDPR_ERASURE_001: Data retention policy required"
}

violation[msg] {
    input.gdpr.erasure_audit_trail == false
    msg := "GDPR_ERASURE_001: Erasure audit trail required"
}

compliant {
    count(violation) == 0
}
