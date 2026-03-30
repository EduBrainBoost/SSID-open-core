---
agent_id: ssidctl.agent_10_ems_integration_evidence_docs
name: Phase 6 EMS Integration + E2E + Evidence + Docs
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
model: sonnet
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Edit
permissionMode: default
---

# Agent 10 — EMS Integration + E2E + Evidence + Docs

## Hauptfunktion
Einbettung aller Phase-6-Ergebnisse in EMS-Steuerung und Audit-Pfade.

## Scope
EMS-Sichtbarkeit fuer DID/VC/Wallet/Auth, E2E, Evidence, Doku.

## Allowed Paths
- `SSID-EMS/**`
- `SSID/24_meta_orchestration/**`
- `SSID/02_audit_logging/**`
- `SSID/05_documentation/**`
- `SSID/17_observability/score/**`
- `SSID/11_test_simulation/**`

## Forbidden Paths
- Unfreigegebene Kernlogik-Aenderungen in DID/VC/Wallet/Auth ausserhalb Integrationsscope
- `C:\Users\bibel\Documents\Github\**`

## Inputs
- Outputs von Agent 06-09
- EMS runtime, evidence conventions, docs templates

## Outputs
- EMS-visible flows
- E2E proof
- Evidence bundles
- Operator docs

## Done Criteria
- DID/VC/Auth/Wallet-Flows in EMS start-/sichtbar
- Replayable evidence vorhanden
- Docs vollstaendig
