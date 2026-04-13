package policies.hash_only

# Policy: HASH_ONLY_DATA_001
# Name: Hash-Only Data Policy
# Rule: Store only hashes, never raw data
# Implementation: Static analysis (Semgrep) + runtime PII-Detector

# Configuration
default storage_type := "invalid"
default hash_algorithm := "none"
default raw_data_retention := "invalid"

# Violation: Non-hash storage detected
violation[msg] {
    input.data_policy.storage_type != "hash_only"
    msg := sprintf("HASH_ONLY_DATA_001: Storage type must be 'hash_only', found '%s'", [input.data_policy.storage_type])
}

# Violation: Unsupported hash algorithm
violation[msg] {
    input.data_policy.hash_algorithm != "SHA3-256"
    input.data_policy.storage_type == "hash_only"
    msg := sprintf("HASH_ONLY_DATA_001: Hash algorithm must be SHA3-256, found '%s'", [input.data_policy.hash_algorithm])
}

# Violation: Non-deterministic hashing
violation[msg] {
    input.data_policy.deterministic == false
    msg := "HASH_ONLY_DATA_001: Hashing must be deterministic for reproducibility"
}

# Violation: Raw data retention detected
violation[msg] {
    input.data_policy.raw_data_retention != "0 seconds"
    input.data_policy.raw_data_retention != "0"
    msg := sprintf("HASH_ONLY_DATA_001: Raw data must be discarded immediately, found retention policy: %s", [input.data_policy.raw_data_retention])
}

# Violation: Missing pepper strategy
violation[msg] {
    input.data_policy.pepper_strategy == ""
    msg := "HASH_ONLY_DATA_001: Pepper strategy required for tenant-specific hash isolation"
}

# Compliance check
compliant {
    count(violation) == 0
    input.data_policy.storage_type == "hash_only"
    input.data_policy.hash_algorithm == "SHA3-256"
    input.data_policy.deterministic == true
    input.data_policy.raw_data_retention == "0 seconds"
    input.data_policy.pepper_strategy != ""
}
