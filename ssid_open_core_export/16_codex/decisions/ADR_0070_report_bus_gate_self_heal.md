# ADR-0070: Report Bus Gate Self-Healing Evidence Backfill

- **Status:** accepted
- **Date:** 2026-03-06
- **Scope:** `.github/workflows/report_bus_gate.yml`

## Context

The `report_bus_gate` workflow runs after merges to verify evidence chain integrity.
When a merge lands without a corresponding evidence record (e.g., due to race conditions
or manual merges), the gate fails permanently for that commit because no backfill exists.

## Decision

Add a `backfill-merges --write --limit 1` step before the evidence chain scan.
This step idempotently creates the missing evidence record for the current merge
if one does not already exist, allowing the gate to proceed.

## Consequences

- Evidence chain gaps from race conditions are self-healed automatically.
- The backfill is idempotent: running it on an already-recorded merge is a no-op.
- No change to the evidence format or WORM guarantees — backfill only appends.
