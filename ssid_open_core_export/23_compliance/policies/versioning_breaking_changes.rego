package policies.versioning_breaking_changes

# Policy: VERSIONING_BREAKING_001
# Name: Versioning & Breaking Changes

violation[msg] {
    not is_semver(input.version.current)
    msg := "VERSIONING_BREAKING_001: Must use MAJOR.MINOR.PATCH format"
}

violation[msg] {
    input.version.breaking_change == true
    input.version.rfc_created == false
    msg := "VERSIONING_BREAKING_001: RFC required for breaking changes"
}

violation[msg] {
    input.version.breaking_change == true
    input.version.migration_guide_published == false
    msg := "VERSIONING_BREAKING_001: Migration guide required"
}

violation[msg] {
    input.version.deprecated == true
    input.version.deprecation_notice_period_days < 180
    msg := "VERSIONING_BREAKING_001: 180-day notice period required"
}

is_semver(v) {
    split(v, ".")[0]
    split(v, ".")[1]
    split(v, ".")[2]
}

compliant {
    count(violation) == 0
}
