package policies.non_custodial

# Policy: NON_CUSTODIAL_001
# Name: Non-Custodial Data Storage
# Rule: NIEMALS Rohdaten von PII oder biometrischen Daten speichern
# Enforcement:
#   - Nur Hash-basierte Speicherung (SHA3-256)
#   - Tenant-spezifische Peppers
#   - Immediate Discard nach Hashing

import data.compliance.constants

# Violation: Raw PII data detected in storage
violation[msg] {
    input.storage.type == "raw"
    input.storage.contains_pii == true
    msg := sprintf("NON_CUSTODIAL_001: Raw PII storage detected in %s. Must use hash-only storage with SHA3-256 and tenant peppers.", [input.storage.location])
}

# Violation: PII stored without hashing
violation[msg] {
    input.data.pii_fields[_]
    input.data.hashed == false
    msg := "NON_CUSTODIAL_001: PII fields must be hashed before storage. Non-custodial code enforcement failed."
}

# Violation: Hash algorithm not SHA3-256
violation[msg] {
    input.storage.hash_algorithm != "SHA3-256"
    input.storage.type == "hashed"
    msg := sprintf("NON_CUSTODIAL_001: Hash algorithm must be SHA3-256, found %s", [input.storage.hash_algorithm])
}

# Violation: No tenant-specific pepper configured
violation[msg] {
    input.storage.type == "hashed"
    input.storage.pepper_strategy != "per_tenant"
    msg := "NON_CUSTODIAL_001: Tenant-specific pepper strategy required for hash-only storage"
}

# Compliance: No violations
compliant {
    count(violation) == 0
}
