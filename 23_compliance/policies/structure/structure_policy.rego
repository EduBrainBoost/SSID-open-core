package structure_policy

# SSID Structure Policy v4.1 - Additional Compliance Rules
# Complements sot_policy.rego with structural enforcement

default allow = false

# Enforce SSID directory structure
deny[msg] {
    some i
    path := input.file_paths[i]
    invalid_ssid_path(path)
    msg := sprintf("STRUCTURE_VIOLATION: invalid SSID path: %s", [path])
}

# Enforce file naming conventions
deny[msg] {
    some i
    file := input.files[i]
    invalid_filename(file.name, file.path)
    msg := sprintf("NAMING_VIOLATION: invalid filename %s in %s", [file.name, file.path])
}

# Enforce shard structure consistency
deny[msg] {
    some i
    shard := input.shards[i]
    missing_shard_components(shard)
    msg := sprintf("SHARD_VIOLATION: shard %s missing required components", [shard.id])
}

# Enforce manifest completeness
deny[msg] {
    some i
    manifest := input.manifests[i]
    incomplete_manifest(manifest)
    msg := sprintf("MANIFEST_VIOLATION: manifest %s missing required fields", [manifest.path])
}

# Helper functions

valid_ssid_layers := {
    "01_foundations",
    "02_audit_logging", 
    "03_core",
    "04_protocols",
    "05_documentation",
    "06_data_pipeline",
    "07_analytics",
    "08_identity_score",
    "09_meta_identity",
    "10_automation",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_verification",
    "15_compliance_base",
    "16_codex",
    "17_roadmap",
    "18_stakeholder",
    "19_adapters",
    "20_integration",
    "21_performance",
    "22_monitoring",
    "23_compliance",
    "24_meta_orchestration"
}

valid_shard_directories := {
    "implementations",
    "tests",
    "docs",
    "contracts",
    "schemas",
    "workflows"
}

invalid_ssid_path(path) {
    not startswith(path, "01_foundations/") and
    not startswith(path, "02_audit_logging/") and
    not startswith(path, "03_core/") and
    not startswith(path, "04_protocols/") and
    not startswith(path, "05_documentation/") and
    not startswith(path, "06_data_pipeline/") and
    not startswith(path, "07_analytics/") and
    not startswith(path, "08_identity_score/") and
    not startswith(path, "09_meta_identity/") and
    not startswith(path, "10_automation/") and
    not startswith(path, "11_test_simulation/") and
    not startswith(path, "12_tooling/") and
    not startswith(path, "13_ui_layer/") and
    not startswith(path, "14_verification/") and
    not startswith(path, "15_compliance_base/") and
    not startswith(path, "16_codex/") and
    not startswith(path, "17_roadmap/") and
    not startswith(path, "18_stakeholder/") and
    not startswith(path, "19_adapters/") and
    not startswith(path, "20_integration/") and
    not startswith(path, "21_performance/") and
    not startswith(path, "22_monitoring/") and
    not startswith(path, "23_compliance/") and
    not startswith(path, "24_meta_orchestration/")
}

invalid_filename(name, path) {
    # Enforce lowercase with underscores for most files
    contains(path, "implementations/") and
    contains(name, ".py") and
    not matches_regex(name, "^[a-z][a-z0-9_]*\\.py$")
}

invalid_filename(name, path) {
    # YAML files should follow conventions
    contains(path, "/") and
    (contains(name, ".yaml") or contains(name, ".yml")) and
    not matches_regex(name, "^[a-z][a-z0-9_-]*\\.(yaml|yml)$")
}

missing_shard_components(shard) {
    not contains(shard.components, "manifest.yaml")
}

missing_shard_components(shard) {
    shard.implementation_required and
    not contains(shard.components, "implementations/")
}

incomplete_manifest(manifest) {
    not contains(manifest.fields, "id")
}

incomplete_manifest(manifest) {
    not contains(manifest.fields, "version")
}

incomplete_manifest(manifest) {
    not contains(manifest.fields, "description")
}

# Allow compliant structures
allow {
    every i
    path := input.file_paths[i]
    not invalid_ssid_path(path)
}

allow {
    every i
    file := input.files[i]
    not invalid_filename(file.name, file.path)
}

allow {
    every i
    shard := input.shards[i]
    not missing_shard_components(shard)
}

allow {
    every i
    manifest := input.manifests[i]
    not incomplete_manifest(manifest)
}