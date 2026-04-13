# Codex / Dokumente und Nachweise

## Purpose

This shard provides Knowledge indexing, schema validation, and documentation registry for the domain **Dokumente und Nachweise**.
It operates under strict non-custodial and hash-only policies as defined
by the SSID architecture.

## Structure

- `chart.yaml` — Shard capability and policy definition (SoT)
- `manifest.yaml` — Deployment and runtime metadata
- `docs/` — Technical documentation
- `tests/` — Automated validation and conformance tests
- `implementations/python/src/` — Reference implementation module

## Interfaces

- Consumes: `03_core` central logic, `23_compliance` rule engine
- Produces: Domain-specific Codex outputs for Dokumente und Nachweise
- Evidence: SHA256 hash-ledger with WORM 10-year retention

## Policies

- **hash_only**: No PII stored; proofs and hashes only
- **non_custodial**: No custody; peer-to-peer flows; autonomous smart contracts

## Status

Draft — pending implementation and promotion gate review.
