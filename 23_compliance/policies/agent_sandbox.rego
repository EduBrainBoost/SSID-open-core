# SSID Agent Sandbox Policy (OPA/Rego)
# Enforces ROOT-24-LOCK, deny-globs, shell whitelist, and HTTP whitelist.

package ssid.agent.sandbox

import future.keywords.if
import future.keywords.in
import future.keywords.contains

# ---------- data references ----------
# data.deny_globs     : list of glob strings
# data.shell_whitelist: list of allowed shell commands
# data.http_whitelist : list of allowed domains
# data.repo_root      : absolute path to repo root

# ---------- helpers ----------

valid_path(p) if {
    startswith(p, data.repo_root)
    not path_matches_deny(p)
}

path_matches_deny(p) if {
    some g in data.deny_globs
    glob.match(g, ["/"], p)
}

# ---------- deny rules ----------

deny contains msg if {
    input.tool == "fs_read"
    not valid_path(input.path)
    msg := "fs_read outside root or matches deny glob"
}

deny contains msg if {
    input.tool == "fs_write"
    not valid_path(input.path)
    msg := "fs_write outside root or matches deny glob"
}

deny contains msg if {
    input.tool == "sh"
    not cmd_whitelisted(input.command)
    msg := "sh command not whitelisted"
}

cmd_whitelisted(cmd) if {
    some allowed in data.shell_whitelist
    startswith(cmd, allowed)
}

deny contains msg if {
    input.tool == "http_get"
    not domain_whitelisted(input.domain)
    msg := "http domain not whitelisted"
}

domain_whitelisted(d) if {
    some allowed in data.http_whitelist
    d == allowed
}

# ---------- allow ----------

allow if {
    count(deny) == 0
}
