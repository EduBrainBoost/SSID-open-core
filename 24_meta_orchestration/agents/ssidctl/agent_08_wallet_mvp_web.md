---
agent_id: ssidctl.agent_08_wallet_mvp_web
name: Phase 6 Wallet MVP Web
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

# Agent 08 — Wallet MVP Web

## Hauptfunktion
Web Wallet MVP: lokale Schluessel, QR-Flows, Consent, Credential Inbox.

## Scope
Web Wallet MVP, lokale Schluessel, QR-Flows, Consent, Credential Inbox.

## Allowed Paths
- `SSID/13_ui_layer/**`
- `SSID/09_meta_identity/**`
- `SSID/10_interoperability/**`
- `SSID/11_test_simulation/**`
- `SSID-EMS/**` — read-only Integration Touchpoints

## Forbidden Paths
- Serverseitige Custody
- Mobile App first
- `C:\Users\bibel\Documents\Github\**`

## Inputs
- DID/VC runtime (Output von Agent 06/07)
- UX constraints, consent rules
- Recovery model

## Outputs
- Wallet MVP
- QR exchange flow
- Local key management integration
- UI tests

## Done Criteria
- Web-Wallet lokal nutzbar
- Credentials empfangbar/praesentierbar
- Kein Custody-Bruch
