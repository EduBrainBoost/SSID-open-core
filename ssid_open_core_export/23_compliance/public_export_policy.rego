# public_export_policy.rego — OPA Policy for SSID Open Core Export
# Validates that exported artifacts comply with open-core rules.

package ssid.opencore.export

import future.keywords.in
import future.keywords.if

# Canonical allowed roots for open-core export (all 24 roots after Root-24 scaffolding)
allowed_roots := {
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
}

# File extensions that must never be exported
blocked_extensions := {
    ".env", ".pem", ".key", ".p12", ".pfx",
    ".jks", ".secret", ".credentials", ".token",
}

# Content patterns that indicate secrets
secret_patterns := {
    "PRIVATE KEY",
    "API_KEY=",
    "SECRET=",
    "PASSWORD=",
    "Bearer ",
    "sk-",
}

# RULE: Root directory must be in allowed set
root_allowed if {
    input.root in allowed_roots
}

# RULE: File extension must not be blocked
extension_allowed if {
    not input.extension in blocked_extensions
}

# RULE: File content must not contain secret patterns
content_clean if {
    every pattern in secret_patterns {
        not contains(input.content, pattern)
    }
}

# RULE: No PII may be present (must be hashed)
pii_compliant if {
    input.pii_check == "clean"
}

# AGGREGATE: Export is allowed only if all rules pass
export_allowed if {
    root_allowed
    extension_allowed
    content_clean
    pii_compliant
}

# Denial reasons for debugging
deny[msg] if {
    not root_allowed
    msg := sprintf("Root '%s' is not in the allowed set", [input.root])
}

deny[msg] if {
    not extension_allowed
    msg := sprintf("Extension '%s' is blocked", [input.extension])
}

deny[msg] if {
    not content_clean
    msg := "File content contains potential secret patterns"
}

deny[msg] if {
    not pii_compliant
    msg := "File contains unmasked PII data"
}
