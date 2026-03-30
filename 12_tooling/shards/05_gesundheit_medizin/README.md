# Tooling - Gesundheit & Medizin

## Purpose

This shard provides Developer tooling, CLI runners, configuration validation, and evidence emission utilities within the domain of health and medicine.
It operates under strict non-custodial and hash-only constraints as defined
by the SSID architecture.

## Structure

- `chart.yaml` - Shard capability definition and policies
- `manifest.yaml` - Deployment and runtime configuration
- `implementations/python/src/` - Python reference implementation
- `tests/` - Automated test suite
- `docs/` - Technical documentation

## Interfaces

- Consumes: `03_core` central logic, `23_compliance` rule engine
- Produces: Evidence hashes, audit logs, domain-specific results
- Registry: `24_meta_orchestration` for shard discovery

## Policies

- **hash_only**: No PII stored; only SHA3-256 proofs and hashes
- **non_custodial**: Peer-to-peer flows; no custody of user data

## Status

Draft - Minimum substance implementation.
