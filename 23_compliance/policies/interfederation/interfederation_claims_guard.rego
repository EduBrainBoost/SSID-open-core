# SSID Interfederation Claims Guard
# Denies any report/doc containing bidirectional/mutual claims
# unless a valid cross-repo proof snapshot exists.
#
# Output: deny[msg] — each msg is a finding string.

package ssid.interfederation_claims_guard

import rego.v1

forbidden_claims := [
    "interfederation active",
    "interfederation certified",
    "mutual validation complete",
    "bidirectional verification achieved",
    "co-truth protocol active",
    "proof nexus certified",
    "cross-system verified",
]

default proof_exists := false

proof_exists if {
    input.proof_snapshot
    input.proof_snapshot.ssid_commit != ""
    input.proof_snapshot.opencore_commit != ""
    count(input.proof_snapshot.file_hashes) > 0
}

deny[msg] if {
    some doc in input.documents
    some claim in forbidden_claims
    contains(lower(doc.content), claim)
    not proof_exists
    msg := sprintf(
        "INTERFEDERATION_CLAIM_WITHOUT_PROOF: '%s' in %s — proof snapshot required",
        [claim, doc.path],
    )
}

deny[msg] if {
    some doc in input.documents
    regex.match(`\d+[%/]\d*\s*(interfed|mutual|co-truth)`, lower(doc.content))
    msg := sprintf(
        "INTERFEDERATION_SCORE_CLAIM: numeric score for interfederation in %s — scores forbidden",
        [doc.path],
    )
}
