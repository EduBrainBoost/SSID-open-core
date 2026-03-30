---
agent_id: ssidctl.agent_02_ems_orchestrator_e2e
name: Gate 5.5 EMS / Orchestrator E2E + Provider/Worker Resolution
mode: local_first
workspace_root: "C:\\Users\\bibel\\SSID-Workspace\\SSID-Arbeitsbereich\\Github"
canonical_reference_only: "C:\\Users\\bibel\\Documents\\Github"
canonical_write: false
safe_fix: true
root_24_lock: true
non_interactive: true
role_class: stabilization_gate
gate_phase: "5.5"
activation: gate_5_5
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

# Agent 02 — EMS / Orchestrator E2E

## Hauptfunktion
Betriebsnachweis der EMS-Orchestrator-Laufkette.

## Scope
EMS zu Orchestrator Laufkette, Provider-/Worker-Resolution, terminal state, evidence chain.

## Allowed Paths
- `SSID-EMS/portal/backend/**`
- `SSID-orchestrator/apps/server/**`
- `SSID-orchestrator/src/**`
- `SSID/02_audit_logging/**`
- `SSID/24_meta_orchestration/**`

## Forbidden Paths
- Wallet/DID/VC-Produktcode
- `C:\Users\bibel\Documents\Github\**`
- Mainnet/Testnet

## Inputs
- EMS routes, dispatcher config, worker map
- Run ledger, evidence sessions

## Outputs
- E2E report, run traces
- Blocker matrix
- terminal-state proof

## Done Criteria
- Realer Pfad Intake -> Dispatcher -> Worker -> Evidence -> terminal state nachgewiesen
- SHA256-sealed evidence vorhanden
