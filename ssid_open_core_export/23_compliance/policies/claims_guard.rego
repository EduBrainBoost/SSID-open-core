package claims_guard

# SSID Claims Guard v1.0
# Denies unverified interfederation/certification/execution claims.
# Only PASS/FAIL + findings. No scores, no badges.

default allow = true

# Forbidden claim patterns — deny if found in any scanned content
# without corresponding evidence/registry flag.

forbidden_claims := [
    "INTERFEDERATION_ACTIVE",
    "INTERFEDERATION_CERTIFIED",
    "EXECUTION_READY",
    "PERFECT CERTIFIED",
    "MUTUAL_VALIDATION_COMPLETE",
    "BIDIRECTIONAL_VERIFICATION_ACHIEVED",
    "CO_TRUTH_PROTOCOL_ACTIVE",
    "PROOF_NEXUS_CERTIFIED",
    "CROSS_SYSTEM_VERIFIED",
    "META_CONTINUUM_READY",
]

deny contains msg if {
    some i
    claim := forbidden_claims[i]
    some j
    file_content := input.scanned_files[j]
    contains(file_content.content, claim)
    not claim_has_evidence(claim)
    msg := sprintf("CLAIMS_GUARD_FAIL: forbidden claim '%s' found in %s without evidence", [claim, file_content.path])
}

# A claim is allowed only if input.evidence_flags explicitly permits it
claim_has_evidence(claim) if {
    some k
    flag := input.evidence_flags[k]
    flag.claim == claim
    flag.verified == true
}
