package sot_policy

# SSID SoT Policy v4.1 - Full Enforcement
# E2: Policy Gate (OPA/REGO) - Structure/Compliance enforcement

# Default deny - explicit allow required
default allow = false

# ROOT-24-LOCK enforcement
allow if {
    not input.security_context == "ROOT-24-LOCK"
    deny[msg]
}

deny contains msg if {
    input.security_context != "ROOT-24-LOCK"
    msg := "ROOT-24-LOCK security context required"
}

# Write-Gate enforcement - path allowlist checking
deny contains msg if {
    some i
    changed_file := input.changed_files[i]
    not allowed_path(changed_file.path)
    msg := sprintf("WRITE_GATE_VIOLATION: path not allowed: %s", [changed_file.path])
}

allowed_path(path) if {
    some j
    allowed := input.allowed_paths[j]
    startswith(path, allowed)
}

# Duplicate-Guard enforcement
deny contains msg if {
    duplicate_rule_id(input.yaml_files)
    msg := "DUPLICATE_GUARD_FAIL: duplicate rule_id found"
}

deny contains msg if {
    duplicate_function_name(input.python_files)
    msg := "DUPLICATE_GUARD_FAIL: duplicate python function names found"
}

deny contains msg if {
    duplicate_rego_rule(input.rego_files)
    msg := "DUPLICATE_GUARD_FAIL: duplicate rego rule_id found"
}

deny contains msg if {
    duplicate_cli_flag(input.cli_files)
    msg := "DUPLICATE_GUARD_FAIL: duplicate CLI flags found"
}

# SoT artifact synchronization enforcement
deny contains msg if {
    sot_file_changed(input.changed_files)
    missing_canonical_sot(input.canonical_sot_files)
    msg := "SOT_GATE_FAIL: canonical SoT file missing after change"
}

deny contains msg if {
    sot_file_changed(input.changed_files)
    inconsistent_sot_artifacts(input.canonical_sot_files)
    msg := "SOT_GATE_FAIL: SoT artifacts not synchronized"
}

# Core logic protection
deny contains msg if {
    some i
    changed_file := input.changed_files[i]
    core_logic_file(changed_file.path)
    not core_logic_explicitly_allowed(changed_file.path, input.allowed_paths)
    msg := sprintf("CORE_LOGIC_VIOLATION: core logic file changed without explicit permission: %s", [changed_file.path])
}

# Evidence logging enforcement
deny contains msg if {
    not input.evidence_mode == "hash-only"
    msg := "EVIDENCE_VIOLATION: hash-only evidence mode required"
}

deny contains msg if {
    some i
    artifact := input.evidence_artifacts[i]
    not hash_only_artifact(artifact)
    msg := sprintf("EVIDENCE_VIOLATION: non-hash-only artifact not allowed: %s", [artifact])
}

# Data Minimization Enforcement
deny contains msg if {
    input.log_mode != "MINIMAL"
    input.log_mode != "FORENSIC"
    msg := "DATA_MINIMIZATION_VIOLATION: log_mode must be MINIMAL or FORENSIC"
}

deny contains msg if {
    input.prompt_persisted == true
    msg := "DATA_MINIMIZATION_VIOLATION: prompt persistence not allowed"
}

deny contains msg if {
    input.stdout_persisted == true
    msg := "DATA_MINIMIZATION_VIOLATION: stdout persistence not allowed"
}

deny contains msg if {
    some i
    log_entry := input.log_entries[i]
    log_entry.contains_prompt == true
    msg := "DATA_MINIMIZATION_VIOLATION: prompt in log entry not allowed"
}

deny contains msg if {
    input.sandbox_not_cleaned == true
    msg := "DATA_MINIMIZATION_VIOLATION: sandbox not cleaned after task completion"
}

# Helper functions
allowed_path(path) if {
    some j
    allowed := input.allowed_paths[j]
    startswith(path, allowed)
}

duplicate_rule_id(yaml_files) if {
    count(yaml_files) > 0
    some i, j
    i != j
    yaml_files[i].rule_id == yaml_files[j].rule_id
}

duplicate_function_name(python_files) if {
    count(python_files) > 0
    some i, j
    i != j
    python_files[i].function_name == python_files[j].function_name
}

duplicate_rego_rule(rego_files) if {
    count(rego_files) > 0
    some i, j
    i != j
    rego_files[i].rule_id == rego_files[j].rule_id
}

duplicate_cli_flag(cli_files) if {
    count(cli_files) > 0
    some i, j
    i != j
    cli_files[i].flag == cli_files[j].flag
}

sot_file_changed(changed_files) if {
    some i
    changed_file := changed_files[i]
    canonical_sot_file(changed_file.path)
}

canonical_sot_file(path) if {
    path == "03_core/validators/sot/sot_validator_core.py"
}

canonical_sot_file(path) if {
    path == "23_compliance/policies/sot/sot_policy.rego"
}

canonical_sot_file(path) if {
    path == "16_codex/contracts/sot/sot_contract.yaml"
}

canonical_sot_file(path) if {
    path == "12_tooling/cli/sot_validator.py"
}

canonical_sot_file(path) if {
    path == "11_test_simulation/tests_compliance/test_sot_validator.py"
}

canonical_sot_file(path) if {
    path == "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md"
}

missing_canonical_sot(canonical_files) if {
    some i
    canonical_file := canonical_files[i]
    not canonical_file.exists
}

inconsistent_sot_artifacts(canonical_files) if {
    # Add consistency checks for SoT artifacts
    # For now, just check if they all exist
    false
}

core_logic_file(path) if {
    startswith(path, "03_core/validators/")
}

core_logic_file(path) if {
    startswith(path, "12_tooling/cli/")
}

core_logic_file(path) if {
    path == "12_tooling/cli/ssid_dispatcher.py"
}

core_logic_explicitly_allowed(path, allowed_paths) if {
    some i
    allowed := allowed_paths[i]
    path == allowed
}

hash_only_artifact(artifact) if {
    artifact == "patch.sha256"
}

hash_only_artifact(artifact) if {
    artifact == "hash_manifest.json"
}

hash_only_artifact(artifact) if {
    artifact == "manifest.json"
}

hash_only_artifact(artifact) if {
    artifact == "gate_status.json"
}

# SOT_AGENT_006: Root 01 AI Layer structure enforcement
deny contains msg if {
    input.root01_must_paths_missing[_]
    msg := "SOT_AGENT_006_FAIL: Root 01 AI Layer MUST paths missing"
}

# SOT_AGENT_007: Root 01 AI Layer shadow-file guard
deny contains msg if {
    input.root01_forbidden_paths_found[_]
    msg := "SOT_AGENT_007_FAIL: Root 01 AI Layer forbidden shadow files detected"
}

# SOT_AGENT_008: Root 01 AI Layer interface wiring
deny contains msg if {
    input.root01_interface_targets_missing[_]
    msg := "SOT_AGENT_008_FAIL: Root 01 AI Layer central interface targets missing"
}

deny contains msg if {
    input.root01_interface_refs_missing[_]
    msg := "SOT_AGENT_008_FAIL: Root 01 AI Layer module.yaml missing interface references"
}

# SOT_AGENT_009: Root 02 Audit Logging structure enforcement
deny contains msg if {
    input.root02_must_paths_missing[_]
    msg := "SOT_AGENT_009_FAIL: Root 02 Audit Logging MUST paths missing"
}

# SOT_AGENT_010: Root 02 Audit Logging shadow-file guard
deny contains msg if {
    input.root02_forbidden_paths_found[_]
    msg := "SOT_AGENT_010_FAIL: Root 02 Audit Logging forbidden shadow files detected"
}

# SOT_AGENT_011: Root 02 Audit Logging interface wiring
deny contains msg if {
    input.root02_interface_targets_missing[_]
    msg := "SOT_AGENT_011_FAIL: Root 02 Audit Logging central interface targets missing"
}

deny contains msg if {
    input.root02_interface_refs_missing[_]
    msg := "SOT_AGENT_011_FAIL: Root 02 Audit Logging module.yaml missing interface references"
}

# SOT_AGENT_012: Root 03 Core structure enforcement
deny contains msg if {
    input.root03_must_paths_missing[_]
    msg := "SOT_AGENT_012_FAIL: Root 03 Core MUST paths missing"
}

# SOT_AGENT_013: Root 03 Core shadow-file guard
deny contains msg if {
    input.root03_forbidden_paths_found[_]
    msg := "SOT_AGENT_013_FAIL: Root 03 Core forbidden shadow files detected"
}

# SOT_AGENT_014: Root 03 Core interface wiring
deny contains msg if {
    input.root03_interface_targets_missing[_]
    msg := "SOT_AGENT_014_FAIL: Root 03 Core central interface targets missing"
}

deny contains msg if {
    input.root03_interface_refs_missing[_]
    msg := "SOT_AGENT_014_FAIL: Root 03 Core module.yaml missing interface references"
}

# SOT_AGENT_015: Root 04 Deployment structure enforcement
deny contains msg if {
    input.root04_must_paths_missing[_]
    msg := "SOT_AGENT_015_FAIL: Root 04 Deployment MUST paths missing"
}

# SOT_AGENT_016: Root 04 Deployment shadow-file guard
deny contains msg if {
    input.root04_forbidden_paths_found[_]
    msg := "SOT_AGENT_016_FAIL: Root 04 Deployment forbidden shadow files detected"
}

# SOT_AGENT_017: Root 04 Deployment interface wiring
deny contains msg if {
    input.root04_interface_targets_missing[_]
    msg := "SOT_AGENT_017_FAIL: Root 04 Deployment central interface targets missing"
}

deny contains msg if {
    input.root04_interface_refs_missing[_]
    msg := "SOT_AGENT_017_FAIL: Root 04 Deployment module.yaml missing interface references"
}

# SOT_AGENT_018: Root 05 Documentation structure enforcement
deny contains msg if {
    input.root05_must_paths_missing[_]
    msg := "SOT_AGENT_018_FAIL: Root 05 Documentation MUST paths missing"
}

# SOT_AGENT_019: Root 05 Documentation shadow-file guard
deny contains msg if {
    input.root05_forbidden_paths_found[_]
    msg := "SOT_AGENT_019_FAIL: Root 05 Documentation forbidden shadow files detected"
}

# SOT_AGENT_020: Root 05 Documentation interface wiring
deny contains msg if {
    input.root05_interface_targets_missing[_]
    msg := "SOT_AGENT_020_FAIL: Root 05 Documentation central interface targets missing"
}

deny contains msg if {
    input.root05_interface_refs_missing[_]
    msg := "SOT_AGENT_020_FAIL: Root 05 Documentation module.yaml missing interface references"
}

# SOT_AGENT_021: Root 06 Data Pipeline structure enforcement
deny contains msg if {
    input.root06_must_paths_missing[_]
    msg := "SOT_AGENT_021_FAIL: Root 06 Data Pipeline MUST paths missing"
}

# SOT_AGENT_022: Root 06 Data Pipeline shadow-file guard
deny contains msg if {
    input.root06_forbidden_paths_found[_]
    msg := "SOT_AGENT_022_FAIL: Root 06 Data Pipeline forbidden shadow files detected"
}

# SOT_AGENT_023: Root 06 Data Pipeline interface wiring
deny contains msg if {
    input.root06_interface_targets_missing[_]
    msg := "SOT_AGENT_023_FAIL: Root 06 Data Pipeline central interface targets missing"
}

deny contains msg if {
    input.root06_interface_refs_missing[_]
    msg := "SOT_AGENT_023_FAIL: Root 06 Data Pipeline module.yaml missing interface references"
}

# SOT_AGENT_024: Root 07 Governance Legal investment_disclaimers.yaml
deny contains msg if {
    input.root07_investment_disclaimers_missing == true
    msg := "SOT_AGENT_024_FAIL: Root 07 investment_disclaimers.yaml missing"
}

# SOT_AGENT_025: Root 07 Governance Legal approval_workflow.yaml
deny contains msg if {
    input.root07_approval_workflow_missing == true
    msg := "SOT_AGENT_025_FAIL: Root 07 approval_workflow.yaml missing"
}

# SOT_AGENT_026: Root 07 Governance Legal regulatory_map_index.yaml
deny contains msg if {
    input.root07_regulatory_map_index_missing == true
    msg := "SOT_AGENT_026_FAIL: Root 07 regulatory_map_index.yaml missing"
}

# SOT_AGENT_027: Root 07 Governance Legal legal_positioning.md
deny contains msg if {
    input.root07_legal_positioning_missing == true
    msg := "SOT_AGENT_027_FAIL: Root 07 legal_positioning.md missing"
}

# SOT_AGENT_028: Root 07 Governance Legal README.md
deny contains msg if {
    input.root07_readme_missing == true
    msg := "SOT_AGENT_028_FAIL: Root 07 README.md missing"
}


# SOT_AGENT_029: Root 08 Identity Score module.yaml
deny contains msg if {
    input.root08_module_yaml_missing == true
    msg := "SOT_AGENT_029_FAIL: Root 08 module.yaml missing"
}

# SOT_AGENT_030: Root 08 Identity Score README.md
deny contains msg if {
    input.root08_readme_missing == true
    msg := "SOT_AGENT_030_FAIL: Root 08 README.md missing"
}

# SOT_AGENT_031: Root 08 Identity Score docs/
deny contains msg if {
    input.root08_docs_dir_missing == true
    msg := "SOT_AGENT_031_FAIL: Root 08 docs/ directory missing"
}

# SOT_AGENT_032: Root 08 Identity Score src/
deny contains msg if {
    input.root08_src_dir_missing == true
    msg := "SOT_AGENT_032_FAIL: Root 08 src/ directory missing"
}

# SOT_AGENT_033: Root 08 Identity Score tests/
deny contains msg if {
    input.root08_tests_dir_missing == true
    msg := "SOT_AGENT_033_FAIL: Root 08 tests/ directory missing"
}

# SOT_AGENT_034: Root 08 Identity Score models/
deny contains msg if {
    input.root08_models_dir_missing == true
    msg := "SOT_AGENT_034_FAIL: Root 08 models/ directory missing"
}

# SOT_AGENT_035: Root 08 Identity Score rules/
deny contains msg if {
    input.root08_rules_dir_missing == true
    msg := "SOT_AGENT_035_FAIL: Root 08 rules/ directory missing"
}

# SOT_AGENT_036: Root 08 Identity Score api/
deny contains msg if {
    input.root08_api_dir_missing == true
    msg := "SOT_AGENT_036_FAIL: Root 08 api/ directory missing"
}

# Allow rule for compliant requests
allow if {
    input.security_context == "ROOT-24-LOCK"
    all_write_paths_allowed(input.changed_files, input.allowed_paths)
    no_duplicates(input)
    sot_sync_compliant(input.changed_files, input.canonical_sot_files)
    core_logic_protected(input.changed_files, input.allowed_paths)
    evidence_compliant(input)
    data_minimization_compliant(input)
}

all_write_paths_allowed(changed_files, allowed_paths) if {
    every changed_file in changed_files {
        allowed_path(changed_file.path)
    }
}

no_duplicates(ctx) if {
    not duplicate_rule_id(ctx.yaml_files)
    not duplicate_function_name(ctx.python_files)
    not duplicate_rego_rule(ctx.rego_files)
    not duplicate_cli_flag(ctx.cli_files)
}

sot_sync_compliant(changed_files, canonical_files) if {
    not sot_file_changed(changed_files)
    not missing_canonical_sot(canonical_files)
}

core_logic_protected(changed_files, allowed_paths) if {
    every changed_file in changed_files {
        core_logic_compliant(changed_file.path, allowed_paths)
    }
}

core_logic_compliant(path, allowed_paths) if {
    not core_logic_file(path)
}

core_logic_compliant(path, allowed_paths) if {
    core_logic_file(path)
    core_logic_explicitly_allowed(path, allowed_paths)
}

evidence_compliant(ctx) if {
    ctx.evidence_mode == "hash-only"
    every artifact in ctx.evidence_artifacts {
        hash_only_artifact(artifact)
    }
}

data_minimization_compliant(ctx) if {
    ctx.log_mode == "MINIMAL"
    ctx.log_mode == "FORENSIC"
    ctx.prompt_persisted == false
    ctx.stdout_persisted == false
    ctx.sandbox_not_cleaned == false
}
