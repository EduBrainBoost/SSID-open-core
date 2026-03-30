---
agent_id: ssidctl.agent_07_vc_runtime_status_revocation
name: Phase 6 VC Runtime + Status/Revocation
mode: local_first
workspace_root: "C:\\Users\\bibel\\SSID-Workspace\\SSID-Arbeitsbereich\\Github"
canonical_reference_only: "C:\\Users\\bibel\\Documents\\Github"
canonical_write: false
safe_fix: true
root_24_lock: true
non_interactive: true
role_class: identity_core_build
gate_phase: "6"
activation: after_gate_5_5_pass
model: opus
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Edit
permissionMode: default
---

# Agent 07 — VC Runtime + Status/Revocation

## Hauptfunktion
Verifiable Credentials Runtime: Issuance, Verification, Presentation, Status/Revocation.

## Scope
VC issuance, verification, presentation, status/revocation.

## Allowed Paths
- `SSID/09_meta_identity/**`
- `SSID/10_interoperability/**`
- `SSID/23_compliance/**`
- `SSID/11_test_simulation/**`
- `SSID/16_codex/**`

## Forbidden Paths
- Wallet surface
- Mainnet
- `C:\Users\bibel\Documents\Github\**`
- PII on-chain

## Inputs
- VC DM 2.0, SD-JWT/BBS+ decision
- Issuer/verifier policy hooks
- Status list models

## Outputs
- VC runtime
- Verification flows
- Revocation/status handling
- Test evidence

## Done Criteria
- issue/verify/present/revoke lauffaehig
- Evidence nachvollziehbar
- Policy checks aktiv
