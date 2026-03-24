# SSID-open-core — Repository Rules

## REPOSITORY IDENTITY
- Repository name: SSID-open-core
- Repository path: <repo-root>
- Primary branch: main
- Working branches: develop, feature/*, fix/*

## WRITE SCOPE
Write only inside this repository.
This repository contains public libraries, SDKs, shared types, and reusable APIs.
Do not place private, internal, or operational project code here.

## FORBIDDEN PATHS
- Other repositories
- Direct writes to .git/
- Global machine-specific files
- Private implementation details from non-public systems
- Local workspace or user-specific files

## CONTENT AND PURPOSE
- Public APIs and type definitions
- Reusable libraries and SDKs
- Shared utilities and helper modules
- Public-safe documentation and validation logic
- No private or proprietary core implementation

## VERSIONING
Semantic Versioning applies.
Breaking changes require explicit approval and coordinated updates for downstream consumers.

## PORTS
This repository does not own or expose runtime service ports.
Libraries and SDKs must not start servers by default.

## SAFE CHANGE RULE
Safe, minimal, deterministic changes only.
Do not introduce secrets, local paths, machine-specific settings, or private references.
