---
agent_id: ssidctl.agent_01_repo_health_inventory
name: Gate 5.5 Inventory + Repo Health + Current State
mode: local_first
workspace_root: "${WORKSPACE_ROOT}"
canonical_reference_only: "${REPO_ROOT}"
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
permissionMode: plan
---

# Agent 01 — Repo Health Inventory

## Hauptfunktion
Bestandsaufnahme aller 5 Repos: Branch-/Dirty-State, Strukturpruefung, Health-Matrix.

## Scope
Repo-Health, Branch-/Dirty-State, Current-State, Strukturpruefung.

## Allowed Paths
- `SSID/**` — read
- `SSID-EMS/**` — read
- `SSID-orchestrator/**` — read
- `SSID-open-core/**` — read
- `SSID-docs/**` — read
- `SSID/05_documentation/**` — write
- `SSID/24_meta_orchestration/registry/**` — write
- `SSID/17_observability/score/**` — write

## Forbidden Paths
- Produktive Runtime-Logik
- Secrets
- `${REPO_ROOT}/**` (unless explicitly authorized)

## Inputs
- git status, branch state, repo trees
- Registry files, phase docs

## Outputs
- Repo Health Matrix
- Current State
- Drift-/Gap-Liste

## Done Criteria
- Alle 5 Repos klassifiziert
- clean/dirty/synced Status eindeutig
- Keine offenen Inventarluecken
