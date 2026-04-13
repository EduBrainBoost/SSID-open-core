# Zugang und Berechtigungen — Codex Overview

## Scope

Provides Knowledge indexing, schema validation, and documentation registry within the Zugang und Berechtigungen domain.

## Architecture

This shard follows the SSID non-custodial, hash-only architecture.
All operations produce SHA256 evidence entries for audit compliance.

## Key Capabilities

- Domain-specific Codex functions for Zugang und Berechtigungen
- Integration with 03_core and 17_observability
- EU AI Act and GDPR compliant data handling

## Dependencies

- `03_core`: Central business logic
- `23_compliance`: Regulatory rule engine
- `24_meta_orchestration`: Service registry
