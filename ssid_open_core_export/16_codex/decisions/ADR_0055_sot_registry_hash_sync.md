# ADR-0055: SoT Registry Hash Sync after Rego Cleanup

Date: 2026-03-03
Status: Accepted
Decider: EduBrainBoost

## Context
PR #9 (`fix/rego-semantics-cleanup-v2`) cleaned up `sot_policy.rego` (removed
duplicate rules, fixed allow/log_mode semantics). The rego file hash changed but
`sot_registry.json` was not updated, causing `sot_autopilot` CI to fail with
"Mismatched hashes: 1".

## Decision
Update `sot_registry.json` entry for `sot_policy_rego` with the correct SHA256
hash of the cleaned-up rego file.

## Consequences
- `sot_diff_alert.py --write` returns PASS
- No functional change to gate behavior
- Registry remains single source of truth for SoT artifact integrity
