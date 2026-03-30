---
agent_id: ssidctl.agent_04_config_secrets_runtime_hygiene
name: Gate 5.5 Config + Secrets + Runtime Hygiene
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

# Agent 04 — Config / Secrets / Runtime Hygiene

## Hauptfunktion
Security-/Config-Haertung, Pfadkorrektur, Secret-Hygiene, fail-closed-Checks.

## Scope
Pfade, Env, Secrets-Hygiene, fail-open/fail-closed, Runtime-Konfig.

## Allowed Paths
- `SSID/**/cli/**`
- `SSID/**/scripts/**`
- `SSID-EMS/portal/backend/**`
- `SSID-orchestrator/apps/server/**`
- `.env*` nur wenn im Scope und erlaubt

## Forbidden Paths
- Echte Secrets committen
- Globale User-Configs
- `C:\Users\bibel\Documents\Github\**`

## Inputs
- env files, config.ts, runtime maps
- Auth guards, secret scan findings

## Outputs
- Hardened config diff
- Path-fix report
- Security hygiene report

## Done Criteria
- Workspace-Pfade korrekt
- fail-open entfernt
- Dev-Env-Hygiene sauber
- Keine offensichtlichen Secret-Leaks
