# CLAUDE.md — SSID-open-core Governance Rules

## Identity

- **Repo**: SSID-open-core
- **Purpose**: Public open-core derivative of the SSID Self-Sovereign Identity Platform
- **Scope**: 5 open-source root modules (03_core, 12_tooling, 16_codex, 23_compliance, 24_meta_orchestration)
- All other SSID roots are private and not part of this repository
- Primary branch: main
- Working branches: develop, feature/*, fix/*

## Write Scope

- Write only inside this repository
- Only within the 5 allowed roots: 03_core, 12_tooling, 16_codex, 23_compliance, 24_meta_orchestration
- Public APIs and type definitions
- Reusable libraries and SDKs
- Shared utilities and helper modules
- Public-safe documentation and validation logic
- No private or proprietary core implementation

## Forbidden

- Writing to other repositories
- Direct writes to .git/
- Global machine-specific files
- Private implementation details from non-public systems
- Local workspace or user-specific files
- Storing secrets, local paths, or machine-specific settings

## Stack

- TypeScript, Python
- Semantic Versioning enforced
- Breaking changes require explicit approval and coordinated updates for downstream consumers

## Ports

This repository does not own or expose runtime service ports. Libraries and SDKs must not start servers by default.

## Rules

- **SAFE-FIX**: Safe, minimal, deterministic changes only. SHA256-logged write enforcement
- **NON-CUSTODIAL**: No PII, hash-only references
- **LOCAL-FIRST**: build, test, verify, commit, push
