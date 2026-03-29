# CLAUDE.md — SSID-open-core Governance Rules

## Identity

- **Repo**: SSID-open-core
- **Purpose**: Public libraries, SDKs, shared types, and reusable APIs for the SSID ecosystem
- **Scope**: Open-source components consumed by SSID-EMS, SSID-orchestrator, and external integrators
- Primary branch: main
- Working branches: develop, feature/*, fix/*

## Write Scope

- Write only inside this repository
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
