package policies.secrets_management

# Policy: SECRETS_MGMT_001
# Name: Secrets Management

violation[msg] {
    input.secrets.in_git == true
    msg := "SECRETS_MGMT_001: Secrets must not be in Git"
}

violation[msg] {
    input.secrets.vault_enabled == false
    msg := "SECRETS_MGMT_001: Vault must be configured"
}

violation[msg] {
    input.secrets.rotation_enabled == false
    msg := "SECRETS_MGMT_001: Rotation must be enabled"
}

violation[msg] {
    input.secrets.rotation_days > 90
    msg := "SECRETS_MGMT_001: Rotation <= 90 days required"
}

compliant {
    count(violation) == 0
}
