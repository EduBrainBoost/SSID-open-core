package sot_policy

base_input := {
  "security_context": "ROOT-24-LOCK",
  "changed_files": [],
  "allowed_paths": [],
  "yaml_files": [],
  "python_files": [],
  "rego_files": [],
  "cli_files": [],
  "canonical_sot_files": [],
  "evidence_mode": "hash-only",
  "evidence_artifacts": ["patch.sha256", "hash_manifest.json", "manifest.json", "gate_status.json"],
  "log_mode": "MINIMAL",
  "prompt_persisted": false,
  "stdout_persisted": false,
  "log_entries": [],
  "sandbox_not_cleaned": false
}

test_deny_empty_for_compliant_input if {
  deny_entries := data.sot_policy.deny with input as base_input
  count(deny_entries) == 0
}

test_deny_non_empty_for_invalid_security_context if {
  deny_entries := data.sot_policy.deny with input as object.union(base_input, {"security_context": "INVALID"})
  count(deny_entries) > 0
}

test_allow_true_for_compliant_input if {
  data.sot_policy.allow with input as base_input
}

test_allow_true_for_forensic_log_mode if {
  data.sot_policy.allow with input as object.union(base_input, {"log_mode": "FORENSIC"})
}

test_deny_for_invalid_log_mode if {
  deny_entries := data.sot_policy.deny with input as object.union(base_input, {"log_mode": "INVALID"})
  count(deny_entries) > 0
}
