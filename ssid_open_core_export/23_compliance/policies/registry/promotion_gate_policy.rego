package data.ssid.promotion_gate

# SSID Cross-Repo Promotion Gate Policy v1.0.0
# Ensures artifacts promoted from canonical (SSID) to derivative (SSID-open-core)
# are complete, hash-consistent, scope-compliant, and free of forbidden patterns.
# Input schema:
#   input.canonical_artifacts[]:  {name, path, hash_sha256, evidence_ref, source_of_truth_ref, on_disk}
#   input.derivative_artifacts[]: {name, path, hash_sha256, on_disk}
#   input.export_scopes[]:        list of allowed path prefixes (strings)
#   input.forbidden_patterns[]:   list of forbidden path patterns (strings)

# Default deny - explicit allow required
default allow = false

# --------------------------------------------------------------------------- #
# RULE 1: PROMO_ENFORCE_001 — missing_required_export_artifact
# Canonical artifact on_disk=true but no derivative artifact with same path
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    canonical := input.canonical_artifacts[i]
    canonical.on_disk == true
    not derivative_path_exists(canonical.path)
    msg := sprintf("PROMO_ENFORCE_001: missing required export artifact — canonical '%s' (%s) is on disk but has no derivative counterpart", [canonical.name, canonical.path])
}

# --------------------------------------------------------------------------- #
# RULE 2: PROMO_ENFORCE_002 — unexpected_derivative_artifact
# Derivative artifact path does not exist in canonical artifacts
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    derivative := input.derivative_artifacts[i]
    not canonical_path_exists(derivative.path)
    msg := sprintf("PROMO_ENFORCE_002: unexpected derivative artifact — '%s' (%s) has no canonical source", [derivative.name, derivative.path])
}

# --------------------------------------------------------------------------- #
# RULE 3: PROMO_ENFORCE_003 — forbidden_public_artifact
# Derivative artifact path matches a forbidden pattern
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    derivative := input.derivative_artifacts[i]
    some j
    pattern := input.forbidden_patterns[j]
    contains(derivative.path, pattern)
    msg := sprintf("PROMO_ENFORCE_003: forbidden public artifact — '%s' (%s) matches forbidden pattern '%s'", [derivative.name, derivative.path, pattern])
}

# --------------------------------------------------------------------------- #
# RULE 4: PROMO_ENFORCE_004 — canonical_derivative_hash_drift
# Canonical and derivative share same path but have different hash_sha256
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    canonical := input.canonical_artifacts[i]
    some j
    derivative := input.derivative_artifacts[j]
    canonical.path == derivative.path
    canonical.hash_sha256
    derivative.hash_sha256
    canonical.hash_sha256 != derivative.hash_sha256
    msg := sprintf("PROMO_ENFORCE_004: hash drift between canonical and derivative for '%s' (%s) — canonical=%s derivative=%s", [canonical.name, canonical.path, canonical.hash_sha256, derivative.hash_sha256])
}

# --------------------------------------------------------------------------- #
# RULE 5: PROMO_ENFORCE_005 — export_scope_violation
# Derivative artifact path not under any allowed export scope
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    derivative := input.derivative_artifacts[i]
    not path_in_export_scope(derivative.path)
    msg := sprintf("PROMO_ENFORCE_005: export scope violation — '%s' (%s) is not under any allowed export scope", [derivative.name, derivative.path])
}

# --------------------------------------------------------------------------- #
# WARNINGS
# --------------------------------------------------------------------------- #

# Canonical artifact without evidence_ref being exported (audit gap)
warn contains msg if {
    some i
    canonical := input.canonical_artifacts[i]
    canonical.on_disk == true
    derivative_path_exists(canonical.path)
    not canonical.evidence_ref
    msg := sprintf("PROMO_WARN_001: canonical artifact exported without evidence_ref (audit gap): %s (%s)", [canonical.name, canonical.path])
}

warn contains msg if {
    some i
    canonical := input.canonical_artifacts[i]
    canonical.on_disk == true
    derivative_path_exists(canonical.path)
    canonical.evidence_ref == ""
    msg := sprintf("PROMO_WARN_001: canonical artifact exported with empty evidence_ref (audit gap): %s (%s)", [canonical.name, canonical.path])
}

# --------------------------------------------------------------------------- #
# VIOLATIONS (aggregated)
# --------------------------------------------------------------------------- #

violations contains violation if {
    some msg
    deny[msg]
    violation := {"severity": "ERROR", "message": msg}
}

violations contains violation if {
    some msg
    warn[msg]
    violation := {"severity": "WARN", "message": msg}
}

# --------------------------------------------------------------------------- #
# ALLOW — all checks pass
# --------------------------------------------------------------------------- #

allow if {
    count(deny) == 0
    all_canonical_exported(input.canonical_artifacts)
    no_unexpected_derivatives(input.derivative_artifacts)
    no_forbidden_derivatives(input.derivative_artifacts)
    all_hashes_consistent_cross_repo(input.canonical_artifacts, input.derivative_artifacts)
    all_derivatives_in_scope(input.derivative_artifacts)
}

# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

# Check if a path exists in derivative artifacts
derivative_path_exists(path) if {
    some i
    input.derivative_artifacts[i].path == path
}

# Check if a path exists in canonical artifacts
canonical_path_exists(path) if {
    some i
    input.canonical_artifacts[i].path == path
}

# Check if a path falls under any allowed export scope
path_in_export_scope(path) if {
    some i
    scope := input.export_scopes[i]
    startswith(path, scope)
}

# Check if a path matches any forbidden pattern
path_matches_forbidden(path) if {
    some i
    pattern := input.forbidden_patterns[i]
    contains(path, pattern)
}

# Aggregate helper: all on-disk canonical artifacts have derivative counterparts
all_canonical_exported(artifacts) if {
    every artifact in artifacts {
        canonical_exported(artifact)
    }
}

canonical_exported(artifact) if {
    artifact.on_disk == false
}

canonical_exported(artifact) if {
    artifact.on_disk == true
    derivative_path_exists(artifact.path)
}

# Aggregate helper: no derivative without canonical source
no_unexpected_derivatives(derivatives) if {
    every derivative in derivatives {
        canonical_path_exists(derivative.path)
    }
}

# Aggregate helper: no derivative matches forbidden pattern
no_forbidden_derivatives(derivatives) if {
    every derivative in derivatives {
        not path_matches_forbidden(derivative.path)
    }
}

# Aggregate helper: all matching canonical/derivative pairs have consistent hashes
all_hashes_consistent_cross_repo(canonicals, derivatives) if {
    every canonical in canonicals {
        every derivative in derivatives {
            cross_hash_consistent(canonical, derivative)
        }
    }
}

cross_hash_consistent(canonical, derivative) if {
    canonical.path != derivative.path
}

cross_hash_consistent(canonical, derivative) if {
    canonical.path == derivative.path
    not canonical.hash_sha256
}

cross_hash_consistent(canonical, derivative) if {
    canonical.path == derivative.path
    not derivative.hash_sha256
}

cross_hash_consistent(canonical, derivative) if {
    canonical.path == derivative.path
    canonical.hash_sha256
    derivative.hash_sha256
    canonical.hash_sha256 == derivative.hash_sha256
}

# Aggregate helper: all derivative artifact paths are within export scopes
all_derivatives_in_scope(derivatives) if {
    every derivative in derivatives {
        path_in_export_scope(derivative.path)
    }
}
