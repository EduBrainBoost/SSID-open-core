package data.ssid.registry_enforcement

# SSID Registry Enforcement Policy v1.0.0
# Ensures all artifacts are registered, hash-consistent, and properly referenced.
# Input schema:
#   input.artifacts[]: {name, path, hash_sha256, evidence_ref, source_of_truth_ref, on_disk, disk_hash}
#   input.guards[]:    {name, unknown_value_behavior}  ("skip" | "fail")

# Default deny - explicit allow required
default allow = false

# --------------------------------------------------------------------------- #
# RULE 1: unregistered_artifact
# Artifact exists on disk but has no registry entry (on_disk=true, missing hash_sha256)
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    artifact := input.artifacts[i]
    artifact.on_disk == true
    not artifact.hash_sha256
    msg := sprintf("REGISTRY_ENFORCE_001: unregistered artifact on disk: %s (%s)", [artifact.name, artifact.path])
}

# --------------------------------------------------------------------------- #
# RULE 2: hash_drift
# SHA256 mismatch between disk hash and registry hash
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    artifact := input.artifacts[i]
    artifact.on_disk == true
    artifact.hash_sha256
    artifact.disk_hash
    artifact.hash_sha256 != artifact.disk_hash
    msg := sprintf("REGISTRY_ENFORCE_002: hash drift detected for %s (%s) — registry=%s disk=%s", [artifact.name, artifact.path, artifact.hash_sha256, artifact.disk_hash])
}

# --------------------------------------------------------------------------- #
# RULE 3: missing_evidence_ref
# Artifact without evidence_ref
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    artifact := input.artifacts[i]
    not artifact.evidence_ref
    msg := sprintf("REGISTRY_ENFORCE_003: missing evidence_ref for artifact: %s (%s)", [artifact.name, artifact.path])
}

deny contains msg if {
    some i
    artifact := input.artifacts[i]
    artifact.evidence_ref == ""
    msg := sprintf("REGISTRY_ENFORCE_003: empty evidence_ref for artifact: %s (%s)", [artifact.name, artifact.path])
}

# --------------------------------------------------------------------------- #
# RULE 4: missing_source_of_truth_ref
# SoT artifact without source_of_truth_ref
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    artifact := input.artifacts[i]
    is_sot_artifact(artifact)
    not artifact.source_of_truth_ref
    msg := sprintf("REGISTRY_ENFORCE_004: missing source_of_truth_ref for SoT artifact: %s (%s)", [artifact.name, artifact.path])
}

deny contains msg if {
    some i
    artifact := input.artifacts[i]
    is_sot_artifact(artifact)
    artifact.source_of_truth_ref == ""
    msg := sprintf("REGISTRY_ENFORCE_004: empty source_of_truth_ref for SoT artifact: %s (%s)", [artifact.name, artifact.path])
}

# --------------------------------------------------------------------------- #
# RULE 5: fail_open_behavior
# Guard/Validator that silently skips unknown values instead of failing
# --------------------------------------------------------------------------- #

deny contains msg if {
    some i
    guard := input.guards[i]
    guard.unknown_value_behavior == "skip"
    msg := sprintf("REGISTRY_ENFORCE_005: fail-open behavior detected in guard %s — unknown_value_behavior must be 'fail', got 'skip'", [guard.name])
}

deny contains msg if {
    some i
    guard := input.guards[i]
    not valid_unknown_value_behavior(guard.unknown_value_behavior)
    msg := sprintf("REGISTRY_ENFORCE_005: invalid unknown_value_behavior '%s' in guard %s — must be 'fail'", [guard.unknown_value_behavior, guard.name])
}

# --------------------------------------------------------------------------- #
# WARNINGS
# --------------------------------------------------------------------------- #

# Artifact registered but not on disk (stale entry)
warn contains msg if {
    some i
    artifact := input.artifacts[i]
    artifact.on_disk == false
    artifact.hash_sha256
    msg := sprintf("REGISTRY_WARN_001: artifact registered but not on disk: %s (%s)", [artifact.name, artifact.path])
}

# Non-SoT artifact with source_of_truth_ref set (unexpected, possibly miscategorized)
warn contains msg if {
    some i
    artifact := input.artifacts[i]
    not is_sot_artifact(artifact)
    artifact.source_of_truth_ref
    artifact.source_of_truth_ref != ""
    msg := sprintf("REGISTRY_WARN_002: non-SoT artifact has source_of_truth_ref set: %s (%s)", [artifact.name, artifact.path])
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
    all_artifacts_registered(input.artifacts)
    all_hashes_consistent(input.artifacts)
    all_evidence_refs_present(input.artifacts)
    all_sot_refs_present(input.artifacts)
    all_guards_fail_closed(input.guards)
}

# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

# SoT artifact detection — paths matching canonical SoT locations
is_sot_artifact(artifact) if {
    startswith(artifact.path, "03_core/validators/sot/")
}

is_sot_artifact(artifact) if {
    startswith(artifact.path, "23_compliance/policies/sot/")
}

is_sot_artifact(artifact) if {
    startswith(artifact.path, "16_codex/contracts/sot/")
}

is_sot_artifact(artifact) if {
    startswith(artifact.path, "12_tooling/cli/sot_")
}

is_sot_artifact(artifact) if {
    startswith(artifact.path, "11_test_simulation/tests_compliance/test_sot_")
}

# Valid unknown_value_behavior values
valid_unknown_value_behavior("fail")

# Aggregate helper: all artifacts on disk are registered
all_artifacts_registered(artifacts) if {
    every artifact in artifacts {
        artifact_registered(artifact)
    }
}

artifact_registered(artifact) if {
    artifact.on_disk == false
}

artifact_registered(artifact) if {
    artifact.on_disk == true
    artifact.hash_sha256
}

# Aggregate helper: all hashes are consistent
all_hashes_consistent(artifacts) if {
    every artifact in artifacts {
        hash_consistent(artifact)
    }
}

hash_consistent(artifact) if {
    artifact.on_disk == false
}

hash_consistent(artifact) if {
    not artifact.disk_hash
}

hash_consistent(artifact) if {
    artifact.on_disk == true
    artifact.hash_sha256
    artifact.disk_hash
    artifact.hash_sha256 == artifact.disk_hash
}

# Aggregate helper: all evidence refs present
all_evidence_refs_present(artifacts) if {
    every artifact in artifacts {
        evidence_ref_present(artifact)
    }
}

evidence_ref_present(artifact) if {
    artifact.evidence_ref
    artifact.evidence_ref != ""
}

# Aggregate helper: all SoT artifacts have source_of_truth_ref
all_sot_refs_present(artifacts) if {
    every artifact in artifacts {
        sot_ref_present(artifact)
    }
}

sot_ref_present(artifact) if {
    not is_sot_artifact(artifact)
}

sot_ref_present(artifact) if {
    is_sot_artifact(artifact)
    artifact.source_of_truth_ref
    artifact.source_of_truth_ref != ""
}

# Aggregate helper: all guards fail-closed
all_guards_fail_closed(guards) if {
    every guard in guards {
        guard.unknown_value_behavior == "fail"
    }
}
