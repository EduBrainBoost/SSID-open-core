package admin.rbac

# SSID Admin Dashboard RBAC Policy
# Roles: superadmin, auditor, operator, viewer

default allow := false

allow if {
    input.role == "superadmin"
}

allow if {
    input.role == "auditor"
    input.action in {"read", "audit", "export"}
}

allow if {
    input.role == "operator"
    input.action in {"read", "write", "execute"}
}

allow if {
    input.role == "viewer"
    input.action == "read"
}

# Jurisdiction blacklist enforcement
deny if {
    input.jurisdiction in {"IR", "KP", "SY", "CU", "RU_CRIMEA", "RU_DNR", "RU_LNR"}
}
