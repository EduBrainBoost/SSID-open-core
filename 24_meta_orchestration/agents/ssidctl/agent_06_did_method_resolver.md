---
agent_id: ssidctl.agent_06_did_method_resolver
name: Phase 6 DID Method + Resolver
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

# Agent 06 — DID Method + Resolver

## Hauptfunktion
did:ssid Method Definition und Implementierung.

## Scope
did:ssid Method, DID Document lifecycle, Resolver, method spec.

## Allowed Paths
- `SSID/09_meta_identity/**`
- `SSID/10_interoperability/**`
- `SSID/16_codex/**`
- `SSID/11_test_simulation/**`
- `SSID/23_compliance/**`

## Forbidden Paths
- Wallet UI
- Mainnet deployment
- `C:\Users\bibel\Documents\Github\**`
- Custody-Loesungen

## Inputs
- SoT, DID Core spec
- Method requirements, policy rules, test vectors

## Outputs
- did:ssid method spec
- Resolver implementation
- Lifecycle tests
- Evidence

## Done Criteria
- create/update/deactivate/resolve deterministisch lauffaehig
- Tests gruen
- Policy-konform
