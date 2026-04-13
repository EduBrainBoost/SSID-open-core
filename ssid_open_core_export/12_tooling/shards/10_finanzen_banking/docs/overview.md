# Finanzen & Banking - Technical Overview

## Scope

Tooling capabilities applied to the finance and banking domain.

## Architecture

This shard follows the SSID non-custodial pattern:
all data references are SHA3-256 hashes. No PII is stored or transmitted.

## Key Components

- **ToolRunner**: Core logic class for finance and banking operations
- **Evidence Trail**: SHA256-based audit logging for every operation
- **Policy Enforcement**: hash_only and non_custodial policies enforced at runtime

## Dependencies

- `03_core` for foundational logic
- `23_compliance` for regulatory rule evaluation
- `17_observability` for metrics and tracing
